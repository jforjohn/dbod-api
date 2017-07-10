#!/usr/bin/python
import multiprocessing as mp
from kafka import KafkaConsumer
from kafka.coordinator.assignors.roundrobin import RoundRobinPartitionAssignor
from elasticsearch import Elasticsearch, helpers
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
import ConfigParser
from functools import partial
from os import getpid

class Initialize:
  def SetupES(self, escluster):
    loggerIndex.info('Connecting to Elasticsearch cluster')
    try:
      es = Elasticsearch(escluster,
            http_auth=('elastic', 'changeme'),
            #sniff_on_start=True,
            #sniff_on_connection_fail=True,
            #sniffer_timeout=120
            )
      return es
    except Exception, e:
      loggerConsumer.error("During Elasticsearch cluster instantiation: %s" %e)

  def SetupConsumer(self):
    # To consume latest messages and auto-commit offsets
    loggerConsumer.info('Consumer starts')
    try:
      myConsumer = KafkaConsumer('sflow2',
                              group_id='sflow-myConsumerz',
                              bootstrap_servers=['smonnet-brpr1.cern.ch:9092','smonnet-brpr2.cern.ch:9092'],
                              max_partition_fetch_bytes=20000000,
                              partition_assignment_strategy=[RoundRobinPartitionAssignor])
      return myConsumer
    except Exception, e:
      loggerConsumer.error("During consumer instantiation: %s" %e)

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
    services_ports_str = config.get('smonit','services_ports')
    if services_ports_str:
      services_ports = services_ports_str.split('-')
    else:
      services_ports = []
    for ports in services_ports:
      service_ports = ports.split(',')
      escluster = self.EScluster(service_ports, monitor_nodes)
      mon_instance = Initialize.SetupES(self, escluster)
      esConnections.append(mon_instance)
    return esConnections

  def FilterOutParams(self):
    filterParams = []
    monitor_params_str = config.get('smonit', 'monitor_params')
    if monitor_params_str:
      monitor_params = monitor_params_str.split('-')
    else:
      monitor_params = []
    for param in monitor_params:
      cluster_params = param.split(',')
      '''
      filter_out = []
      i = 0
      while i < len(cluster_params)-1:
        filter_out.append((cluster_params[i], cluster_params[i+1]))
        i += 2
      filterParams.append(filter_out)
      '''
      filterParams.append((cluster_params[0], cluster_params[1]))
    return filterParams



class MessageHandler():
  def __init__(self, es, filter_params):
    child_procs = config.get('smonit', 'child_procs')
    if child_procs:
      child_procs =  child_procs + ',' + str(getpid())
    else:
      child_procs = getpid()
    with open(config_file, 'w') as fd:
      config.set('smonit', 'child_procs', child_procs)
      config.write(fd)

    self.data = dict()
    self.send_data = list()
    self.es = es
    self.filter_params = filter_params
    self.vari = [21]

  def Accept(self, body, message):
    try:
      #self.payload.append(self.EmbedData(body))
      self.EmbedData(body)
    except Exception, e:
      loggerConsumer.error('Discarding message - failed to append to payload: %s' % e)

    #self.Encapsulate()
    #print len(self.send_data)

    if len(self.send_data) >= 3500:
      #topic = message.topic
      self.send_data = filter(None, self.send_data)
      if self.send_data:
        self.PushMessage(self.es)

  def EmbedData(self, body):
    sflowSample = dict()
    '''
    timestamp = 'T'.join(
                str(datetime.datetime.now())
               .split())[0:23] + 'Z'
    '''
    timestamp = int(time.time() * 1000)

    #print timestamp
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
      #[sflow_NEWsrcIP, sflow_NEWdstIP] = map(self.mapIP, [sflow_srcIP,sflow_dstIP])

      [sflow_inputPort,sflow_outputPort,sflow_srcVlan,sflow_dstVlan,sflow_IP_Protocol,sflow_IPTTL,sflow_srcPort,sflow_dstPort,sflow_PacketSize,sflow_IPSize,sflow_SampleRate,sflow_SampleRate] = map(int, [sflow_inputPort,sflow_outputPort,sflow_srcVlan,sflow_dstVlan,sflow_IP_Protocol,sflow_IPTTL,sflow_srcPort,sflow_dstPort,sflow_PacketSize,sflow_IPSize,sflow_SampleRate,sflow_SampleRate])

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
      'sflow_SampleRate':sflow_SampleRate,
      #'sflow_NEWsrcIP':sflow_NEWsrcIP,
      #'sflow_NEWdstIP':sflow_NEWdstIP
      }
      if str(sflowSample.get(self.filter_params[0])) == self.filter_params[1]:
        if self.filter_params[1] == '10.100.0.9':
          print '10.100.0.9'
        [sflow_NEWsrcIP, sflow_NEWdstIP] = map(self.mapIP, [sflow_srcIP,sflow_dstIP])
        sflowSample.update({'sflow_NEWsrcIP': sflow_NEWsrcIP,
                            'sflow_NEWdstIP': sflow_NEWdstIP
                          })
        self.Encapsulate(sflowSample)
      else:
        #sflowSample = {}
        self.send_data.append({})
    else:
      #sflowSample = {}#{'type':body}
      self.send_data.append({})

    #return sflowSample

  def mapIP(self,param):
    try:
      return test[param]
    except:
      return param

  def Encapsulate(self, sample):
    datestr  = time.strftime('%Y.%m.%d')
    indexstr = '%s-%s' % ('sflow', datestr)

    self.send_data.append({
      '_index' : indexstr,
      '_type': 'sflow',
      '_source': sample
    })

    #loggerIndex.info('Compiling Elasticsearch payload with  records') #% len(self.payload))
    #header = json.dumps(header)
    #body   = ''
    #data   = ''

    #for record in self.payload:
    #  data += '%s\n%s\n' % (header, json.dumps(record))

    #return send_data

  def PushMessage(self, es):
    try:
      #r = requests.post('%s/_bulk?' % args.elasticserver, data=data, timeout=args.timeout)
      #helpers.parallel_bulk(es, data, chunk_size=5)
      print self.es
      for success, info in helpers.parallel_bulk(es, self.send_data, chunk_size=3500):
        #print '\n', info, success
        #print info, success
        #print self.vari, success
        if not success:
          print('A document failed:', info)
      self.data = {}
      self.send_data = []
      #loggerIndex.info('Bulk API request to Elasticsearch returned with code ' )
    except Exception, e:
      loggerIndex.error('Failed to send to Elasticsearch: %s' % e)

class StreamConsumer():
  def __init__(self, connection, callback):
    self.callback   = callback
    self.connection = connection
    #self.es = es

  #def close(self, *args, **kwargs):
    #self.connection.close()
    #exit(0)

  def runConsumer(self):
    try:
      for message in self.connection:
        body = message.value #json.loads(message.value)
        self.callback(body, message)
    except Exception, e:
      loggerConsumer.error("During messages parsing exception: %s" %e)

def newMonitor(kafkaConnection, *args):
  config.read(config_file)
  mon_config = MonConfig()
  new_config = config.get('smonit', 'new_monitor').split(',')
  loggerIndex.info("New config arrived: %s" %(new_config))
  '''
  if new_config[0] == 'reload':
    new_esConnection = mon_config.ClusterConnections()
    new_filter_params = mon_config.FilterOutParams()
  else:
  '''
  new_filterParams = (new_config[1], new_config[2])
  monitor_nodes = config.get('smonit', 'monitor_nodes').split(',')
  new_ports = new_config[3:]
  new_cluster = mon_config.EScluster(new_ports, monitor_nodes)
  new_esConnection = mon_config.SetupES(new_cluster)
  p = mp.Process(target=start, args=(kafkaConnection,new_esConnection,new_filterParams))
  p.start()
  print args


def closeConsumer(connection, *args):
  loggerConsumer.info('Signal handler called with signal: %s' %(args))
  # restore the original signal handler as otherwise evil things will happen
  # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
  signal.signal(signal.SIGINT, original_sigint)
  self.connection.close()
  try:
    sys.exit(0)
  except KeyboardInterrupt:
    sys.exit(1)

def start(kafkaConnection, esConnections, filterParams):
  handler = MessageHandler(esConnections, filterParams)
  consumer = StreamConsumer(kafkaConnection, handler.Accept)
  consumer.runConsumer()

if __name__ == '__main__':
  global loggerConsumer
  global loggerIndex
  global test
  #pr_queue = mp.Queue()

  config = ConfigParser.ConfigParser()
  config_file = "/home/smonnet/dbod-api/api.cfg"
  config.read(config_file)
  # set pid in the config file (for receiving later the SIGHUP)
  with open(config_file, 'w') as fd:
    config.set('smonit', 'processing_pid', getpid())
    config.write(fd)

  # create logger
  with open("jsonIPmap.json", 'r') as fd:
    test = json.load(fd)
    #test = yaml.load(fd, Loader=Loader)

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

  mon_config = MonConfig()
  esConnections = mon_config.ClusterConnections()
  filterParams = mon_config.FilterOutParams()
  loggerIndex.info("Initialization: es connections: %s" %(esConnections))
  loggerIndex.info("Filter in params: %s" %(filterParams))

  init_set = Initialize()
  kafkaConnection = init_set.SetupConsumer()

  original_sigint = signal.getsignal(signal.SIGINT)
  signal.signal(signal.SIGHUP, partial(newMonitor, kafkaConnection))
  #signal.signal(signal.SIGINT, partial(closeConsumer, kafkaConnection))
  #start(kafkaConnection, esConnections, filterParams)
  processes =  [mp.Process(target=start,
                args=(kafkaConnection,esConnections[i],filterParams[i]))
                for i in range(len(esConnections))]
  for p in processes:
    #p.daemon = True
    p.start()
  signal.signal(signal.SIGINT, partial(closeConsumer, kafkaConnection))
  #handler = MessageHandler(esConnections, filterParams)
  #consumer = StreamConsumer(kafkaConnection, handler.Accept)
  #consumer.runConsumer()
