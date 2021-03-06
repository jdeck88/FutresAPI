# -*- coding: utf-8 -*-
import csv
import datetime
import json
import os


import elasticsearch.helpers
from elasticsearch import Elasticsearch, RequestsHttpConnection, serializer, compat, exceptions


TYPE = 'record'


# see https://github.com/elastic/elasticsearch-py/issues/374
class JSONSerializerPython2(serializer.JSONSerializer):
    """Override elasticsearch library serializer to ensure it encodes utf characters during json dump.
    See original at: https://github.com/elastic/elasticsearch-py/blob/master/elasticsearch/serializer.py#L42
    A description of how ensure_ascii encodes unicode characters to ensure they can be sent across the wire
    as ascii can be found here: https://docs.python.org/2/library/json.html#basic-usage
    """

    def dumps(self, data):
        # don't serialize strings
        if isinstance(data, compat.string_types):
            return data
        try:
            return json.dumps(data, default=self.default, ensure_ascii=True)
        except (ValueError, TypeError) as e:
            raise exceptions.SerializationError(data, e)


class ESLoader(object):
    def __init__(self, data_dir, index_name, drop_existing=False, alias=None, host='localhost:9200'):
        """
        :param data_dir:
        :param index_name: the es index to upload to
        :param drop_existing:
        :param alias: the es alias to associate the index with
        """
        self.data_dir = data_dir
        self.index_name = index_name
        self.drop_existing = drop_existing
        self.alias = alias
        self.es = Elasticsearch([host], serializer=JSONSerializerPython2())

    def load(self):
        if not self.es.indices.exists(self.index_name):
            print ('creating index ' + self.index_name)
            self.__create_index()
        elif self.drop_existing:
            print('deleting index ' + self.index_name)
            self.es.indices.delete(index=self.index_name)
            print ('creating index ' + self.index_name)
            self.__create_index()

        doc_count = 0
        
        print('searching for files in ' + self.data_dir)
        for file in get_files(self.data_dir):
            try:
                print(file)
                doc_count += self.__load_file(file)
            except RuntimeError as e:
                print(e)
                print("Failed to load file {}".format(file))

        print("Indexed {} documents total".format(doc_count))

    def __load_file(self, file):
        doc_count = 0
        data = []

        with open(file) as f:
            print("Starting indexing on " + f.name)
            reader = csv.DictReader(f)

            for row in reader:
                #TODO: only set location if lat/lng are always set
                #row['location'] = row['decimalLatitude'] + "," + row['decimalLongitude'] 
                data.append({k: v for k, v in row.items() if v})  # remove any empty values

            elasticsearch.helpers.bulk(client=self.es, index=self.index_name, actions=data, doc_type=TYPE,
                                       raise_on_error=True, chunk_size=10000, request_timeout=60)
            doc_count += len(data)
            print("Indexed {} documents in {}".format(doc_count, f.name))

        return doc_count

    def __create_index(self):
        request_body = {
            "mappings": {
                TYPE: {
                    "properties": {
                        "measurementType": {"type": "text"},
                        "decimalLatitude": { "type": "float" },
                        "decimalLongitude": { "type": "float" }
                        #"location": { "type": "geo_point" }                        
                    }
                }
            }
        }
        self.es.indices.create(index=self.index_name, body=request_body)
        #if self.alias:
            #self.es.indices.put_alias(index=self.index_name, name=self.alias)

def get_files(dir, ext='csv'):
    for root, dirs, files in os.walk(dir):

        if len(files) == 0:
            print("no files found in {}".format(dir))

        for file in files:
            if file.endswith(ext):
                yield os.path.join(root, file)


inputDirectory = 'data/'
index = 'futres'
drop_existing = True
alias = 'futres'
host =  'tarly.cyverse.org:80'

loader = ESLoader(inputDirectory, index, drop_existing, alias, host)
loader.load()


