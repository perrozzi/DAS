#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=W0613,W0622,W0702,W0703

"""
DAS DB utilities.
"""

__author__ = "Valentin Kuznetsov"

# system modules
import sys
import time
import threading

# monogo db modules
from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure
import gridfs

# DAS modules
from DAS.utils.utils import genkey, print_exc, dastimestamp
from DAS.utils.das_config import das_readconfig
from DAS.utils.ddict import DotDict

# MongoDB does not allow to store documents whose size more then 4MB
MONGODB_LIMIT = 4*1024*1024

def find_one(col, spec, fields=None):
    "Custom implementation of find_one function for given MongoDB parameters"
    res = None
    try:
        res = [r for r in col.find(spec, fields, exhaust=True)]
    except StopIteration:
        return None
    if  res:
        return res[0]
    return None

def make_uri(pairs):
    """Return MongoDB URI for provided set of dbhost,dbport pairs"""
    uris = []
    for item in pairs:
        dbhost, dbport = item
        if  not dbport:
            uris.append(dbhost)
        else:
            if  not isinstance(dbport, int):
                msg = 'Invalid port="%s", type=%s' % (dbport, type(dbport))
                raise Exception(msg)
            if  dbport <= 1024:
                msg = 'Not enough privileges to use port=%s' % dbport
                raise Exception(msg)
            uris.append('%s:%s' % (dbhost, dbport))
    return 'mongodb://%s' % ','.join(uris)

class DBConnection(object):
    """
    DB Connection class whose purpose is to get MongoDB connection
    """
    def __init__(self):
        # just for the sake of information
        self.instance = "Instance at %d" % self.__hash__()
        self.conndict = {}

    def connection(self, uri):
        """Return MongoDB connection"""
        key = genkey(str(uri))
        if  key not in self.conndict:
            try:
                dbinst = MongoClient(host=uri, w=1,
                        auto_start_request=True, safe=True)
                gfs    = dbinst.gridfs
                fsinst = gridfs.GridFS(gfs)
                self.conndict[key] = (dbinst, fsinst)
            except (ConnectionFailure, AutoReconnect):
                tstamp = dastimestamp('')
                thread = threading.current_thread()
                print "### MongoDB connection failure thread=%s, id=%s, time=%s" \
                        % (thread.name, thread.ident, tstamp)
            except Exception as exc:
                print_exc(exc)
                return None
        return self.conndict[key]

    def is_alive(self, uri):
        "Check if DB connection is alive"
        key = genkey(str(uri))
        try:
            conn, _ = self.connection(uri)
            if  conn:
                _dbnames = conn.database_names()
            else:
                return False
        except:
            if  key in self.conndict:
                del self.conndict[key]
            return False
        return True

DB_CONN_SINGLETON = DBConnection()

def db_connection(uri, singleton=False, verbose=True):
    """Return DB connection instance"""
    dbinst = None
    # loop several times to acquire DB connection
    for idx in xrange(1, 5):
        try:
            if  singleton:
                dbinst, _ = DB_CONN_SINGLETON.connection(uri)
            else:
                dbinst, _ = DBConnection().connection(uri)
        except Exception as exc:
            if  verbose:
                msg = 'Fail to get connection to MongoDB: %s' % str(exc)
                print msg
            pass
        if  dbinst:
            break
        time.sleep(0.1*idx)
    return dbinst

def is_db_alive(uri):
    "Check if DB is alive"
    return DB_CONN_SINGLETON.is_alive(uri)

def db_gridfs(uri):
    """
    Return pointer to MongoDB GridFS
    """
    fsinst = None
    try:
        _, fsinst = DB_CONN_SINGLETON.connection(uri)
    except:
        pass
    return fsinst

def parse2gridfs(gfs, prim_key, genrows, logger=None):
    """
    Yield docs from provided generator with size < 4MB or store them into
    GridFS.
    """
    if  not prim_key:
        return
    key = prim_key.split('.')[0]
    for row in genrows:
        if  not row:
            continue
        row_size = sys.getsizeof(str(row))
        if  row_size < MONGODB_LIMIT:
            yield row
        else:
            fid = gfs.put(str(row))
            gfs_rec = {key: {'gridfs_id': str(fid)}}
            if  logger:
                msg = 'parse2gridfs record size %s, replace with %s'\
                % (row_size, gfs_rec)
                logger.info(msg)
            yield gfs_rec

def create_indexes(coll, index_list):
    """
    Create indexes for provided collection/index_list and
    ensure that they are in place
    """
    index_info = coll.index_information().values()
    for pair in index_list:
        index_exists = 0
        for item in index_info:
            if  item['key'] == [pair]:
                index_exists = 1
        if  not index_exists:
            try:
                if  isinstance(pair, list):
                    coll.create_index(pair)
                else:
                    coll.create_index([pair])
            except Exception as exp:
                print_exc(exp)
        try:
            if  isinstance(pair, list):
                coll.ensure_index(pair)
            else:
                coll.ensure_index([pair])
        except Exception as exp:
            print_exc(exp)

def db_monitor(uri, func, sleep=5):
    """
    Check status of MongoDB connection. Invoke provided function upon
    successfull connection.
    """
    conn = db_connection(uri)
    while True:
        if  not conn or not is_db_alive(uri):
            try:
                conn = db_connection(uri)
                func()
                if  conn:
                    print "### db_monitor re-established connection %s" % conn
                else:
                    print "### db_monitor, lost connection"
            except:
                pass
        time.sleep(sleep)


def get_db_uri():
    """ returns default dburi from config """
    config = das_readconfig()
    return config['mongodb']['dburi']


def query_db(dbname, dbcol, query,  idx=0, limit=10):
    """
    query a given db collection
    """

    conn = db_connection(get_db_uri())
    col = conn[dbname][dbcol]

    if col:
        try:
            if limit == -1:
                for row in col.find(query, exhaust=True):
                    yield row
            else:
                for row in col.find(query).skip(idx).limit(limit):
                    yield row
        except Exception as exc:  # we shall not catch GeneratorExit
            print_exc(exc)
