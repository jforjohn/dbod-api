#!/usr/bin/python
from kafka import KafkaConsumer
from kafka.coordinator.assignors.roundrobin import RoundRobinPartitionAssignor
from elasticsearch import Elasticsearch, helpers, RequestsHttpConnection
#from translateIP import mapIP
import logging
import signal
import socket
import sys
import json
import yaml
from yaml import load
from yaml import CLoader as Loader
import time, datetime
from os import getpid
import ConfigParser
import pandas as pd
#from dbod.config import config, config_file

class Initialize:
  def SetupES(self, escluster):
    loggerIndex.info("Connecting to Elasticsearch cluster: %s" %(escluster))
    try:
      es = (Elasticsearch(escluster,
                http_auth = ('elastic', 'changeme'),
                connection_class=RequestsHttpConnection
                #sniff_on_start=True,
                #sniff_on_connection_fail=True,
                #sniffer_timeout=120
                ))
    except Exception, e:
      loggerConsumer.error("During Elasticsearch cluster instantiation: %s" %e)
    return es

  def SetupConsumer(self):
    # To consume latest messages and auto-commit offsets
    loggerConsumer.info('Consumer starts')
    try:
      myConsumer = KafkaConsumer('sflow2',
                              group_id='sflow-myConsumerz',
                              bootstrap_servers=['smonnet-brpr1.cern.ch:9092','smonnet-brpr2.cern.ch:9092'],
                              max_partition_fetch_bytes=20000000,
                              partition_assignment_strategy=[RoundRobinPartitionAssignor])
    except Exception, e:
      loggerConsumer.error("During consumer instantiation: %s" %e)
    return myConsumer

class MonConfig(Initialize):
  def EScluster(self, service_ports, monitor_nodes):
    monitor_nodes_len = len(monitor_nodes)
    service_ports_len = len(service_ports)
    maxi = max(monitor_nodes_len, service_ports_len)
    mini = min(monitor_nodes_len, service_ports_len)
    for i in range(mini, maxi):
      if monitor_nodes_len < maxi:
        monitor_nodes.append(monitor_nodes[i % monitor_nodes_len])
        monitor_nodes_len = maxi
      elif service_ports_len < maxi:
        service_ports.append(service_ports[i % service_ports_len])

    escluster = [monitor_nodes[i] + ':' + service_ports[i]
               for i in range(monitor_nodes_len)
              ]
    return escluster

  def ClusterConnections(self):
    esConnections = []
    monitor_nodes = config.get('smonit','monitor_nodes').split(',')
    services_ports = config.get('smonit','services_ports').split('-')
    for ports in services_ports:
      service_ports = ports.split(',')
      escluster = self.EScluster(service_ports, monitor_nodes)
      mon_instance = Initialize.SetupES(self, escluster)
      esConnections.append(mon_instance)
    return esConnections

  def FilterOutParams(self):
    filterParams = []
    monitor_params = config.get('smonit', 'monitor_params').split('-')
    for param in monitor_params:
      cluster_params = param.split(',')
      filter_out = []
      i = 0
      while i < len(cluster_params)-1:
        filter_out.append((cluster_params[i], cluster_params[i+1]))
        i += 2
      filterParams.append(filter_out)
    return filterParams


class MessageHandler():
  def __init__(self, es, filter_params):
    self.es = es
    self.filter_params = filter_params
    self.send_data = [[]] * len(es)
    self.vari = [21]

  def NewMonitor(self, *args):
    config.read(config_file)
    mon_config = MonConfig()
    new_config = config.get('smonit', 'new').split(',')
    print new_config
    if new_config[0] == 'reload':
      self.es = mon_config.ClusterConnections()
      print self.es
      self.filter_params = mon_config.FilterOutParams()
    else:
      loggerConsumer.info("Updating with new config %s" %(new_config))
      new_filters = [(new_config[1], new_config[2])]
      self.filter_params.append(new_filters)
      monitor_nodes = config.get('smonit', 'monitor_nodes').split(',')
      new_ports = new_config[3:]
      new_cluster = mon_config.EScluster(new_ports, monitor_nodes)
      self.es.append(new_cluster)
      self.send_data.append([])
    print args
    loggerConsumer.info("New cluster %s and filters %s" %(self.es, self.filter_params))
    return

  def Accept(self, body, message):
    signal.signal(signal.SIGHUP, self.NewMonitor)
    try:
      #self.payload.append(self.EmbedData(body))
      for i in range(len(self.filter_params)):
        cluster_filters = self.filter_params[i]
        self.send_data[i].append(self.EmbedData(body, cluster_filters))
    except Exception, e:
      loggerConsumer.error('Discarding message - failed to append to payload: %s' % e)

    #print len(self.send_data[0])
    if len(self.send_data[0]) >= 2:
      #topic = message.topic
      for i in range(len(self.es)):
        es_cluster = self.es[i]
        data = filter(None, self.send_data[i])
        if len(data) > 0:
          if i == 1:
            print 'ela'
          self.PushMessage(es_cluster, data)

  def EmbedData(self, body, cluster_filters):
    sflowSample = dict()
    '''
    timestamp = 'T'.join(
                str(datetime.datetime.now())
               .split())[0:23] + 'Z'
    '''
    timestamp = int(time.time() * 1000)

    fields = body.split(',')
    if fields[0] == "FLOW":
      sflow_ReporterIP = fields[1]
      sflow_inputPort = fields[2]
      sflow_outputPort = fields[3]
      sflow_srcMAC = fields[4]
      sflow_dstMAC = fields[5]
      sflow_EtherType = fields[6]
      sflow_srcVlan = fields[7]
      sflow_dstVlan = fields[8]
      sflow_srcIP = fields[9]
      try:
        socket.inet_pton(socket.AF_INET, sflow_srcIP)
      except:
        sflow_srcIP = '0.0.0.0'
      sflow_dstIP = fields[10]
      try:
        socket.inet_pton(socket.AF_INET, sflow_dstIP)
      except:
        sflow_dstIP = '0.0.0.0'
      sflow_IP_Protocol = fields[11]
      sflow_IPTOS = fields[12]
      sflow_IPTTL = fields[13]
      sflow_srcPort = fields[14]
      sflow_dstPort = fields[15]
      sflow_tcpFlags = fields[16]
      sflow_PacketSize = fields[17]
      sflow_IPSize = fields[18]
      sflow_SampleRate = fields[19]
      try:
        sflow_counter = fields[20]
      except:
        sflow_counter = -1

      #dateTime = int(time.time()*1000000)

      #[sflow_NEWsrcIP,sflow_NEWdstIP] = map(mapIP, [sflow_srcIP,sflow_dstIP])
      #srcIPnew = mapIP(srcIP)
      #dstIPnew = mapIP(dstIP)

      #[sflow_inputPort,sflow_outputPort,sflow_srcVlan,sflow_dstVlan,sflow_IP_Protocol,sflow_IPTTL,sflow_srcPort,sflow_dstPort,sflow_PacketSize,sflow_IPSize,sflow_SampleRate,sflow_SampleRate] = map(int, [sflow_inputPort,sflow_outputPort,sflow_srcVlan,sflow_dstVlan,sflow_IP_Protocol,sflow_IPTTL,sflow_srcPort,sflow_dstPort,sflow_PacketSize,sflow_IPSize,sflow_SampleRate,sflow_SampleRate])

      sflowSample = {
      '@message':body,
      '@timestamp':timestamp,
      '@version':1,
      'type':'sflow',
      'SampleType':'FLOW',
      'sflow_ReporterIP':sflow_ReporterIP,
      'sflow_inputPort':sflow_inputPort,
      'sflow_outputPort':sflow_outputPort,
      'sflow_srcMAC':sflow_srcMAC,
      'sflow_dstMAC':sflow_dstMAC,
      'sflow_EtherType':sflow_EtherType,
      'sflow_srcVlan':sflow_srcVlan,
      'sflow_dstVlan':sflow_dstVlan,
      'sflow_srcIP':sflow_srcIP,
      'sflow_dstIP':sflow_dstIP,
      'sflow_IP_Protocol':sflow_IP_Protocol,
      'sflow_IPTOS':sflow_IPTOS,
      'sflow_IPTTL':sflow_IPTTL,
      'sflow_srcPort':sflow_srcPort,
      'sflow_dstPort':sflow_dstPort,
      'sflow_tcpFlags':sflow_tcpFlags,
      'sflow_PacketSize':sflow_PacketSize,
      'sflow_IPSize':sflow_IPSize,
      'sflow_SampleRate':sflow_SampleRate
      #'sflow_NEWsrcIP':sflow_NEWsrcIP,
      #'sflow_NEWdstIP':sflow_NEWdstIP
      }

      sample_in = False
      if cluster_filters:
        sample_in = True
        for param in cluster_filters:
          sample_in = (sample_in and (str(sflowSample.get(param[0])) == param[1]))

      if sample_in:
        [sflow_NEWsrcIP, sflow_NEWdstIP] = map(self.mapIP, [sflow_srcIP,sflow_dstIP])
        sflowSample.update({'sflow_NEWsrcIP': sflow_NEWsrcIP,
                            'sflow_NEWdstIP': sflow_NEWdstIP
                          })
        datestr  = time.strftime('%Y.%m.%d')
        indexstr = '%s-%s' % ('sflow', datestr)

        sflowSample = {'_op_type': 'index',
             '_index' : indexstr,
             '_type': 'sflow',
             '_source': sflowSample
             }
      else:
        sflowSample = {}

    else:
      sflowSample = {}

    return sflowSample

  def mapIP(self,param):
    try:
      return test[param]
    except:
      return param

  def Encapsulate(self, sflowSample):
    #loggerIndex.info('Compiling Elasticsearch payload with  records') #% len(self.payload))

    datestr  = time.strftime('%Y.%m.%d')
    indexstr = '%s-%s' % ('sflow', datestr)
    pandasList = pd.DataFrame(sflowSample)
    pandasJson = pandasList.to_json(orient='records')
    return json.loads(pandasJson)
    '''
    header = pandasList.columns
    for i in range(len(pandasList)):
      source_dict = {}
      row = pandasList.iloc[i]
      for k in header:
        source_dict[k] = str(row[k])
      yield {'_op_type': 'index',
             '_index' : indexstr,
             '_type': 'sflow',
             '_source': source_dict
            }
    '''
    #header = json.dumps(header)
    #body   = ''
    #data   = ''

    #for record in self.payload:
    #  data += '%s\n%s\n' % (header, json.dumps(record))

    #return send_data

  def PushMessage(self, es, data):
    #try:
    #r = requests.post('%s/_bulk?' % args.elasticserver, data=data, timeout=args.timeout)
    #helpers.parallel_bulk(es, data, chunk_size=5)
    for success, info in helpers.parallel_bulk(es, data, chunk_size=100):
      #print '\n', info, success
      #print info, success
      #print es
      if not success:
        loggerIndex.error("A document failed: %s" %(info))
    self.send_data = [[]] * len(self.es)
    #loggerIndex.info('Bulk API request to Elasticsearch returned with code ' )
    #except Exception, e:
    #  loggerIndex.error('Failed to send data to Elasticsearch: %s' %(e))

class StreamConsumer():
  def __init__(self, connection, callback):
    self.callback   = callback
    self.connection = connection

  #def close(self, *args, **kwargs):
    #self.connection.close()
    #exit(0)


  def closeConsumer(self, *args):
    loggerConsumer.info('Signal handler called with signal: ' %(args))
    self.connection.close()
    sys.exit(0)

  def runConsumer(self):
    #try:
    for message in self.connection:
      body = message.value #json.loads(message.value)
      self.callback(body, message)
    #except Exception, e:
    #  loggerConsumer.error("During messages parsing exception: %s" %e)


if __name__ == '__main__':
  #def main():
  global loggerConsumer
  global loggerIndex
  global test
  global config
  global config_file

  config = ConfigParser.ConfigParser()
  config_file = "/home/smonnet/dbod-api/api.cfg"
  config.read(config_file)
  # create logger
  stream = open("jsonIPmap.yaml", 'r')
  test = yaml.load(stream, Loader=Loader)

  loggerConsumer = logging.getLogger('kafka consumer')
  loggerConsumer.setLevel(logging.DEBUG)

  loggerIndex = logging.getLogger('es indexing')
  loggerIndex.setLevel(logging.DEBUG)

  # create console handler and set level to debug
  logDest = logging.StreamHandler()

  # create formatter
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

  # add formatter to ch
  logDest.setFormatter(formatter)

  # add ch to logger
  loggerConsumer.addHandler(logDest)
  loggerIndex.addHandler(logDest)

  # set pid in the config file (for receiving later the SIGHUP)
  with open(config_file, 'w') as fd:
    config.set('smonit', 'processing_pid', getpid())
    config.write(fd)

  init_set = Initialize()
  kafkaConnection = init_set.SetupConsumer()

  mon_config = MonConfig()
  esConnections = mon_config.ClusterConnections()
  filterParams = mon_config.FilterOutParams()

  loggerIndex.info("Initialization: es connections: %s and filters: %s"
                   %(esConnections, filterParams))
  #esConnection = SetupES()
  handler = MessageHandler(esConnections, filterParams)

  consumer = StreamConsumer(kafkaConnection, handler.Accept)

  signal.signal(signal.SIGINT, consumer.closeConsumer)

  consumer.runConsumer()
