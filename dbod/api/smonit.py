#!/usr/bin/env python
"""
Metadata module, which includes all the classes related with metadata endpoints.
"""

import tornado.web
import logging
import requests
import json
import base64
from os import kill
import signal

from dbod.api.base import *
from dbod.config import config, config_file

class Smonit(tornado.web.RequestHandler):
    """
    This is the handler of **/smonit/<name>** endpoint.

    This endpoint takes 1 argument:

    * *<name>* - the name of the entity which will be monitored

    Things that are given for the development of this endpoint:

    * We request indirectly a `Postgres <https://www.postgresql.org/>`_ database through `PostgREST <http://postgrest.com/>`_ which returns a response in JSON format
    * The database's table/view that is used for this endpoint is called *metadata* and provides information about the metadata of a database instance(s).

    The request method implemented for this endpoint is just the :func:`post`.

    """
    authentication = "basic " + \
                      base64.b64encode(config.get('api', 'user') + \
                      ":" + config.get('api', 'pass'))
    #TODO make a put and delete method for updating or deleting monitoring clusters
    def post(self, **args):
      """
      Returns the metadata of a host or an instance
      The *GET* method returns the instance(s)' metadata given the *host* or the *database name*.
      (No any special headers for this request)

      :param name: authorized entity to be monitored
      :type name: str
      :param name: the host or database name which is given in the url
      :type name: str
      :rtype: json - the response of the request

              * in case of "*host*" it returns all the instances' metadata that are hosted in the specified host
              * in casse of "*instance*" it returns the metadata of just the given database

      :raises: HTTPError - when the <class> argument is not valid ("host" or "instance") or the given host or database name does not exist or in case of an internal error

      .. note::

        Along with the 'name' should come a default key-value pair with which 'name' is identifiable

      """
      name = args.get('name')
      #TODO  need more checks for any possible existent monitoring instance
      max_params = config.get('smonit','max_param_filters')
      if name:
        monitor_names = config.get('smonit', 'monitor_names')
        if name in monitor_names.split('-'):
          logging.error("The %s is already been registered for monitoring,\
                         if you want update the parameters"
                         %(name))
          #self.set_status(CONFLICT)
          #raise tornado.web.HTTPError(CONFLICT)
        #TODO configure the number of nodes
        no_nodes = self.get_argument('no_nodes', 3)
        if no_nodes < 2:
          logging.warning("The cluster with %s number of nodes is not possible"
                           %(no_nodes))
          no_nodes = 3

        logging.info("A monitoring cluster with %s nodes is gonna be created"
                      %(no_nodes))
        new_ports = []
        for index in range(no_nodes - 1):
          data = self.createInstance(index, name, 'elasticsearch', 'true')
          logging.info("response: %s" %(data))
          port = self.getPort(data)
          if port:
              new_ports.append(str(port))

        data = self.createInstance(index + 1, name,'elasticsearch', 'false')
        port = self.getPort(data)
        if port:
          new_ports.append(str(port))
        _ = self.createInstance(index + 1, name, 'kibana', None)

        monitor_params = config.get('smonit', 'monitor_params')
        services_ports = config.get('smonit', 'services_ports')
        params = ''

        i = 0
        key = self.get_argument('key' + str(i))
        value = self.get_argument('value' + str(i))
        while (key and value) and i <= max_params:
          logging.info("Entity %s wants to filter in %s with value %s"
                       %(name, key, value))
          #TODO Need to check if the filter for the specific cluster already exists
          if params:
            params = params + ',' + key + ',' + value
          else:
            params = key + ',' + value
          i += 1
          key = self.get_argument('key' + str(i), None)
          value = self.get_argument('value' + str(i), None)

        if not params:
          logging.error("At least a pair of key and value is needed in the params")
          raise tornado.web.HTTPError(BAD_REQUEST)

        #if len(new_ports) != (i-1)
        if not new_ports:
          logging.error("The monitoring cluster was not started successfully")
          raise tornado.web.HTTPError(SERVICE_UNAVAILABLE)

        new_ports_str = ','.join(new_ports)
        #TODO write the specific host with the port in the config file
        with open(config_file, 'w') as fd:
          config.set('smonit', 'monitor_names',
                      monitor_names + '-' + name)
          config.set('smonit','monitor_params',
                      monitor_params + '-' + params)
          config.set('smonit', 'services_ports',
                     services_ports + '-' + new_ports_str)
          config.set('smonit','new_monitor',
                     'add,' + params + ',' + new_ports_str)
          config.write(fd)

        logging.info("The '%s' was added for monitoring in %s"
                     %(name, config_file))
        logging.info("The new params are: %s" %(params))
        logging.info("The new ports of the monitoring cluster are: %s"
                      %(new_ports_str))

        logging.debug("The registered names for monitoring are: %s"
                      %(monitor_names))

        processing_pid = config.get('smonit', 'processing_pid')
        kill(int(processing_pid), signal.SIGHUP)
        print processing_pid

      else:
          logging.error("Unsupported endpoint")
          raise tornado.web.HTTPError(BAD_REQUEST)

    def getPort(self, data):
      nodePort = None
      i = 0
      response = data.get('response', [])
      nodePort = None
      while not nodePort and i < len(response):
        if response[i].get('Service'):
          ports = response[i]['Service']['spec'].get('ports')[0]
          if ports.get('port') == 9200:
            nodePort = ports.get('nodePort')
        i += 1
      return nodePort

    def createInstance(self, index, name, app_type, mdi):
      resource_url = config.get('smonit', 'deployment_url')
      payload = {'app_type': app_type,
                 'app_name': name + '-' + app_type + str(index),
                 'CLUSTER_NAME': name,
                 'NODE_MASTER': mdi,
                 'NODE_DATA':  mdi,
                 'NODE_INGEST': mdi,
                 'CLIENT_NODE': name + '-' + 'elasticsearch' + str(index)
                }
      response = requests.post(resource_url,
                               headers={'Authorization': self.authentication},
                               params=payload)
      if response.ok:
        data = response.json()
        self.write(data)
        return data
      elif response.status_code == 409:
        logging.warning("There is already an instance with the same name")
        return {}
      else:
        logging.error("Error in posting in %s with payload %s" %(resource_url, payload))
        raise tornado.web.HTTPError(SERVICE_UNAVAILABLE)
