#!/bin/sh

cd $WMCOREBASE/test/python/WMCore/JobSplitting
#python FileBased_unit.py
cd ../WMBS
#python files_DAOFactory_unit.py
cd ..
python WMException_t.py
cd MsgService_t
python MsgService_t.py
cd ../Agent_t
python Harness_t.py
