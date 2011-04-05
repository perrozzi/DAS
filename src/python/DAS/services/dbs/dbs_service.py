#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
DBS service
"""
__revision__ = "$Id: dbs_service.py,v 1.24 2010/04/09 19:41:23 valya Exp $"
__version__ = "$Revision: 1.24 $"
__author__ = "Valentin Kuznetsov"

import re
import time
from DAS.services.abstract_service import DASAbstractService
from DAS.utils.utils import map_validator, xml_parser, qlxml_parser
from DAS.utils.utils import dbsql_opt_map, convert_datetime

def convert_dot(row, key, attrs):
    """Convert dot notation key.attr into storage one"""
    for attr in attrs:
        if  row.has_key(key) and row[key].has_key(attr):
            name = attr.split('.')[-1]
            row[key][name] = row[key][attr]
            del row[key][attr]

class DBSService(DASAbstractService):
    """
    Helper class to provide DBS service
    """
    def __init__(self, config):
        DASAbstractService.__init__(self, 'dbs', config)
        self.reserved = ['api', 'apiversion']
        self.map = self.dasmapping.servicemap(self.name)
        map_validator(self.map)
        self.prim_instance = 'cms_dbs_prod_global'
        self.instances = ['cms_dbs_prod_global', 'cms_dbs_caf_analysis_01',
                'cms_dbs_ph_analysis_01', 'cms_dbs_ph_analysis_02']

    def url_instance(self, url, instance):
        """
        Adjust URL for a given instance
        """
        if  instance in self.instances:
            return url.replace(self.prim_instance, instance)
        return url
            
    def adjust_params(self, api, kwds):
        """
        Adjust DBS2 parameters for specific query requests
        """
        if  api == 'listPrimaryDatasets':
            pat = kwds['pattern']
            if  pat[0] == '/':
                kwds['pattern'] = pat.split('/')[1]
        if  api == 'listProcessedDatasets':
            pat = kwds['processed_datatset_name_pattern']
            if  pat[0] == '/':
                try:
                    kwds['processed_datatset_name_pattern'] = pat.split('/')[2]
                except:
                    pass
        if  api == 'fakeRelease4Dataset':
            val = kwds['dataset']
            if  val != 'required':
                kwds['query'] = 'find release where dataset=%s' % val
            else:
                kwds['query'] = 'required'
            kwds.pop('dataset')
        if  api == 'fakeConfig':
            val = kwds['dataset']
            sel = 'config.name, config.content, config.version, config.type, config.annotation, config.createdate, config.createby, config.moddate, config.modby'
            if  val != 'required':
                kwds['query'] = 'find %s where dataset=%s' % (sel, val)
            else:
                kwds['query'] = 'required'
            kwds.pop('dataset')
        if  api == 'fakeListDataset4File':
            val = kwds['file']
            if  val != 'required':
                kwds['query'] = "find dataset , count(block), count(file.size), \
  sum(block.size), sum(block.numfiles), sum(block.numevents) \
  where file=%s and dataset.status like VALID*" % val
            else:
                kwds['query'] = 'required'
            kwds.pop('file')
        if  api == 'fakeRun4Run':#runregistry don't support 'in'
            val = kwds['run']
            if  val != 'required':
                if  isinstance(val, dict):
                    minR = 0
                    maxR = 0
                    if  val.has_key('$lte'):
                        maxR = val['$lte']
                    if  val.has_key('$gte'):
                        minR = val['$gte']
                    if  minR and maxR:
                        arr = ','.join((str(r) for r in range(minR, maxR)))
                        val = "run in (%s)" % arr
                    elif val.has_key('$in'):
                        arr = ','.join((str(r) for r in val['$in']))
                        val = 'run in (%s)' % arr
                elif isinstance(val, int):
                    val = "run = %d" % val
                kwds['query'] = "find run where %s" % val
            else:
                kwds['query'] = 'required'
            kwds.pop('run')
        if  api == 'fakeGroup4Dataset':
            val = kwds['dataset']
            if  val != 'required':
                val = "dataset = %s" % val
                kwds['query'] = "find phygrp where %s" % val
            else:
                kwds['query'] = 'required'
            kwds.pop('dataset')
        if  api == 'fakeChild4File':
            val = kwds['file']
            if  val != 'required':
                val = "file = %s" % val
                kwds['query'] = "find file.child where %s" % val
            else:
                kwds['query'] = 'required'
            kwds.pop('file')
        if  api == 'fakeChild4Dataset':
            val = kwds['dataset']
            if  val != 'required':
                val = "dataset = %s" % val
                kwds['query'] = "find dataset.child where %s" % val
            else:
                kwds['query'] = 'required'
            kwds.pop('dataset')
        if  api == 'fakeDataset4Run':#runregistry don't support 'in'
            val = kwds['run']
            qlist = []
            if  val != 'required':
                if  isinstance(val, dict):
                    minR = 0
                    maxR = 0
                    if  val.has_key('$lte'):
                        maxR = val['$lte']
                    if  val.has_key('$gte'):
                        minR = val['$gte']
                    if  minR and maxR:
                        arr = ','.join((str(r) for r in range(minR, maxR)))
                        val = "run in (%s)" % arr
                    elif val.has_key('$in'):
                        arr = ','.join((str(r) for r in val['$in']))
                        val = 'run in (%s)' % arr
                elif isinstance(val, int):
                    val = "run = %d" % val
                if  kwds.has_key('dataset') and kwds['dataset']:
                    val += ' and dataset=%s' % kwds['dataset']
                kwds['query'] = \
                "find dataset where %s and dataset.status like VALID*" % val
            else:
                kwds['query'] = 'required'
            kwds.pop('run')
            kwds.pop('dataset')
        if  api == 'fakeRun4File':
            val = kwds['file']
            if  val != 'required':
                kwds['query'] = "find run where file = %s" % val
            else:
                kwds['query'] = 'required'
            kwds.pop('file')
        if  api == 'fakeDatasetSummary':
            value = ""
            for key, val in kwds.items():
                if  key == 'dataset' and val:
                    pat = re.compile('/.*/.*/.*')
                    if  pat.match(val):
                        if  val.find('*') != -1:
                            value += ' and dataset=%s' % val
                    else:
                        value += ' and dataset=%s' % val
                if  key == 'primary_dataset' and val:
                    value += ' and primds=%s' % val
                if  key == 'release' and val:
                    value += ' and release=%s' % val
                if  key == 'tier' and val:
                    value += ' and tier=%s' % val
                if  key == 'phygrp' and val:
                    value += ' and phygrp=%s' % val
            for key in ['dataset', 'release', 'primary_dataset', 'tier', 'phygrp']:
                try:
                    del kwds[key]
                except:
                    pass
            if  value:
                kwds['query'] = "find dataset, sum(block.numfiles), sum(block.numevents), \
  count(block), sum(block.size) where %s" % value[4:]
            else:
                kwds['query'] = 'required'
        if  api == 'fakeListDatasetbyDate':
#           20110126/{'$lte': 20110126}/{'$lte': 20110126, '$gte': 20110124} 
            query_for_single = "find dataset , count(block), sum(block.size),\
  sum(block.numfiles), sum(block.numevents), dataset.createdate \
  where dataset.createdate %s %s and dataset.status like VALID*"
            query_for_double = "find dataset , count(block), sum(block.size),\
  sum(block.numfiles), sum(block.numevents), dataset.createdate \
  where dataset.createdate %s %s \
  and dataset.createdate %s %s and dataset.status like VALID*"
            val = kwds['date']
            qlist = []
            query = ""
            if val != "required":
                if isinstance(val, dict):
                    for opt in val:
                        nopt = dbsql_opt_map(opt)
                        if nopt == ('in'):
                            self.logger.debug(val[opt])
                            nval = [convert_datetime(x) for x in val[opt]]
                        else:
                            nval = convert_datetime(val[opt])
                        qlist.append(nopt)
                        qlist.append(nval)
                    if len(qlist) == 4:
                        query = query_for_double % tuple(qlist)
                    else:
                        msg = "dbs_services::fakeListDatasetbyDate \
 wrong params get, IN date is not support by DBS2 QL"
                        self.logger.info(msg)
                elif isinstance(val, int):
                    val = convert_datetime(val)
                    query = query_for_single % ('=', val)
                kwds['query'] = query
            else:
                kwds['query'] = 'required'
            kwds.pop('date')
            
    def parser(self, query, dformat, source, api):
        """
        DBS data-service parser.
        """
        if  api == 'listBlocks':
            prim_key = 'block'
        elif api == 'listBlocks4path':
            api = 'listBlocks'
            prim_key = 'block'
        elif api == 'listBlockProvenance':
            prim_key = 'block'
        elif api == 'listFiles':
            prim_key = 'file'
        elif api == 'listLFNs':
            prim_key = 'file_lfn'
        elif api == 'listFileLumis':
            prim_key = 'file_lumi_section'
        elif api == 'listFileProcQuality':
            prim_key = 'file_proc_quality'
        elif api == 'listFileParents':
            prim_key = 'file_parent'
        elif api == 'listTiers':
            prim_key = 'data_tier'
        elif api == 'listDatasetSummary':
            prim_key = 'processed_dataset'
        elif api == 'listDatasetParents':
            prim_key = 'processed_dataset_parent'
        elif api == 'listPrimaryDatasets':
            prim_key = 'primary_dataset'
        elif api == 'listProcessedDatasets':
            prim_key = 'processed_dataset'
        elif api == 'listAlgorithms':
            prim_key = 'algorithm'
        elif api == 'listRuns':
            prim_key = 'run'
        elif  api == 'fakeRelease4Dataset':
            prim_key = 'release'
        elif  api == 'fakeGroup4Dataset':
            prim_key = 'group'
        elif  api == 'fakeConfig':
            prim_key = 'config'
        elif  api == 'fakeListDataset4File':
            prim_key = 'dataset'
        elif  api == 'fakeListDatasetbyDate':
            prim_key = 'dataset'
        elif  api == 'fakeDatasetSummary':
            prim_key = 'dataset'
        elif  api == 'fakeDataset4Run':
            prim_key = 'dataset'
        elif  api == 'fakeRun4File':
            prim_key = 'run'
        elif  api == 'fakeRun4Run':
            prim_key = 'run'
        elif api == 'fakeChild4File':
            prim_key = 'child'
        elif api == 'fakeChild4Dataset':
            prim_key = 'child'
        else:
            msg = 'DBSService::parser, unsupported %s API %s' \
                % (self.name, api)
            raise Exception(msg)
        if  api.find('fake') != -1:
            gen = qlxml_parser(source, prim_key)
        else:
            gen = xml_parser(source, prim_key)
        for row in gen:
            if  not row:
                continue
            if  row.has_key('algorithm'):
                del row['algorithm']['ps_content']
            if  row.has_key('processed_dataset') and \
                row['processed_dataset'].has_key('path'):
                    if  isinstance(row['processed_dataset']['path'], dict) \
                    and row['processed_dataset']['path'].has_key('dataset_path'):
                        path = row['processed_dataset']['path']['dataset_path']
                        del row['processed_dataset']['path']
                        row['processed_dataset']['name'] = path
            # case for fake apis
            # remove useless attribute from results
            if  row.has_key('dataset'):
                if  row['dataset'].has_key('count_file.size'):
                    del row['dataset']['count_file.size']
                if  row['dataset'].has_key('dataset'):
                    name = row['dataset']['dataset']
                    del row['dataset']['dataset']
                    row['dataset']['name'] = name
            if  row.has_key('child') and row['child'].has_key('dataset.child'):
                row['child']['name'] = row['child']['dataset.child']
                del row['child']['dataset.child']
            if  row.has_key('child') and row['child'].has_key('file.child'):
                row['child']['name'] = row['child']['file.child']
                del row['child']['file.child']
            if  row.has_key('run') and row['run'].has_key('run'):
                row['run']['run_number'] = row['run']['run']
                del row['run']['run']
            if  row.has_key('release') and row['release'].has_key('release'):
                row['release']['name'] = row['release']['release']
                del row['release']['release']
            attrs = ['config.name', 'config.content', 'config.version',\
                     'config.type', 'config.annotation', 'config.createdate',\
                     'config.createby', 'config.moddate', 'config.modby']
            convert_dot(row, 'config', attrs)
            yield row
