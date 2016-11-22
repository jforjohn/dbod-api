#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

"""
cluster module, which includes all the classes related with cluster endpoints.
"""

import tornado.web
import logging
import requests
import json

from dbod.api.base import *
from dbod.config import config

class Cluster(tornado.web.RequestHandler):
    """
    This is the handler of **/cluster/<class>/<name>** endpoint.
    This endpoint takes 1 arguments:
    * *<name>* - the name of a *cluster*
    Things that are given for the development of this endpoint:
    * We request indirectly a `Postgres <https://www.postgresql.org/>`_ database through `PostgREST <http://postgrest.com/>`_ which returns a response in JSON format
    * The database's table/view that is used for this endpoint is called *cluster* and provides metadata about a cluster and its instances.
    * Here is an example of this table:
    --ToDO
    The request method implemented for this endpoint is just the :func:`get`.
    """
    def get(self, name):
        """Returns the cluster information
        he *GET* method returns a *cluster* given a *name*.
        (No any special headers for this request)
        :param name: the database name which is given in the url
        :type name: str
        :rtype: json - the response of the request
        :raises: HTTPError - when the given cluster name does not exist or in case of an internal error
        """
        response = requests.get(config.get('postgrest', 'cluster_url') + "?name=eq." + name)
        if response.ok:
            data = response.json()
            if data:
                self.write({'response' : data})
                self.set_status(OK)
            else:
                logging.error("Instance metadata not found: " + name)
                raise tornado.web.HTTPError(NOT_FOUND)
        else:
            logging.error("Entity metadata not found: " + name)
            raise tornado.web.HTTPError(NOT_FOUND)



    @http_basic_auth
    def post(self, name):
        """
        The *POST* method inserts a new cluster into the database with all the
        information that is needed for the creation of it.
        In the request body we specify all the information of the *cluster*
        table along with the *attribute* table. We extract and
        separate the information of each table.
        .. note::
            * It's possible to insert more than one *attribute* in one cluster.
            * The cluster names have to be unique
            * Also, the creation is not successful
                * if the client is not authorized or
                * if there is any internal error
                * if the format of the request body is not right or if there is no *database name* field
        :param name: the new cluster name which is given in the url or any other string
        :type name: str
        :raises: HTTPError - in case of an internal error
        :request body:  json
                       - for *instance*: json
                       - for *attribute*: json
        """
        logging.debug(self.request.body)
        cluster = json.loads(self.request.body)

        # Insert the instance in database using PostREST
        response = requests.post(config.get('postgrest', 'insert_cluster_url'), json=cluster, headers={'Prefer': 'return=representation'})
        if response.ok:
            logging.info("Created cluster " + cluster["in_json"]["name"])
            logging.debug(response.text)
            self.set_status(CREATED)
        else:
            logging.error("Error creating the cluster: " + response.text)
            raise tornado.web.HTTPError(response.status_code)




    @http_basic_auth
    def put(self, name):
        """
        The *PUT* method updates a cluster with all the information that is needed.
        In the request body we specify all the information of the *cluster*
        table along with the *attribute* tables.
        The procedure of this method is the following:
        * We extract and separate the information of each table.
        * We get the *id* of the row from the given (unique) database from the url.
        * If it exists, we delete if any information with that *id* exists in the tables.
        * After that, we insert the information to the related table along with the instance *id*.
        * In case of more than one attributes we insert each one separetely.
        * Finally, we update the *cluster* table's row (which include the given database name) with the new given information.
        :param name: the cluster name which is given in the url
        :type name: str
        :raises: HTTPError - when the *request body* format is not right or in case of internall error
        """
        logging.debug(self.request.body)
        instance = json.loads(self.request.body)
        clusterid = self.__get_cluster_id__(name)
        if not clusterid:
            logging.error("Cluster '" + name + "' doest not exist.")
            raise tornado.web.HTTPError(NOT_FOUND)

        # Check if the attributes are changed
        if "attributes" in instance:
            attributes = instance["attributes"]
            response = requests.delete(config.get('postgrest', 'cluster_attribute_url') + "?cluster_id=eq." + str(clusterid))
            if response.ok or response.status_code == 404:
                if len(attributes) > 0:
                    # Insert the attributes
                    insert_attributes = []
                    for attribute in attributes:
                        insert_attr = {'cluster_id': clusterid, 'name': attribute, 'value': attributes[attribute]}
                        logging.debug("Inserting attribute: " + json.dumps(insert_attr))
                        insert_attributes.append(insert_attr)

                    response = requests.post(config.get('postgrest', 'cluster_attribute_url'), json=insert_attributes)
                    if response.ok:
                        self.set_status(NO_CONTENT)
                    else:
                        logging.error("Error inserting attributes: " + response.text)
                        raise tornado.web.HTTPError(response.status_code)
            else:
                logging.error("Error deleting attributes: " + response.text)
                raise tornado.web.HTTPError(response.status_code)
            del instance["attributes"]

    @http_basic_auth
    def delete(self, id):
        """
        The *DELETE* method deletes a cluster by *name*.
        In order to delete a cluster we have to delete all the related information of the specified database name in *cluster*, *attribute* and *instance* tables.
        :param name: the database name which is given in the url
        :type name: str
        :raises: HTTPError - when the given database name cannot be found
        """
        logging.debug(self.request.body)
        cluster = {'id': id}

        # Insert the instance in database using PostREST
        response = requests.post(config.get('postgrest', 'delete_cluster_url'), json=cluster, headers={'Prefer': 'return=representation'})
        if response.ok:
            logging.info("Delete cluster " + cluster["id"])
            logging.debug(response.text)
            self.set_status(CREATED)
        else:
            logging.error("Error delete the cluster: " + response.text)
            raise tornado.web.HTTPError(response.status_code)

