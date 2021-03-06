#!/usr/bin/env python
"""
_Exists_

MySQL implementation of Files.Exists
"""

__all__ = []



from WMCore.Database.DBFormatter import DBFormatter

class Exists(DBFormatter):
    sql = "select id from wmbs_file_details where lfn = :lfn"

    def format(self, result):
        result = DBFormatter.format(self, result)

        if len(result) == 0:
            return False
        else:
            return result[0][0]

    def getBinds(self, lfn=None):
        return self.dbi.buildbinds(self.dbi.makelist(lfn), "lfn")

    def execute(self, lfn=None, conn = None, transaction = False):
        result = self.dbi.processData(self.sql, self.getBinds(lfn),
                         conn = conn, transaction = transaction)
        return self.format(result)
