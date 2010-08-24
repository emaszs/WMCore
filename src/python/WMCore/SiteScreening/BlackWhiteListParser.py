#!/usr/bin/env python
"""
_BlackWhiteListParser_

Parsing for black and white lists, both SE and CE

Large parts of the July 2008 re-write come from Brian Bockelman

"""

__revision__ = "$Id: BlackWhiteListParser.py,v 1.2 2008/10/15 13:54:10 ewv Exp $"
__version__  = "$Revision: 1.2 $"
__author__   = "ewv@fnal.gov"

import sets
import types
import fnmatch
import re

from WMCore.Services.SiteDB.SiteDB import SiteDBJSON

class BlackWhiteListParser(object):

    """
    A class which applies blacklist and whitelist; designed to allow the user
    to filter out sites.  Allows users to specify only the CMS name from SiteDB
    (and simple wildcards), but internally filters only on the CE/SE name.
    """

    def __init__(self, cfgParams, logger=None):
        self.logger = logger
        self.kind = 'se'
        self.mapper = None # Defined by Super class
        self.siteDBAPI = SiteDBJSON()
        self.blacklist = None
        self.whitelist = None

    def configure(self, cfgParams):
        """
        Load up the black and white list from the configuation parameters
           * EDG.SE/CE_black_list
           * EDG.SE/CE_white_list
        and expand things that SiteDB knows the CMS names for
        """

        self.blacklist = []
        if cfgParams.has_key('EDG.%s_black_list' % self.kind):
            userInput = cfgParams['EDG.%s_black_list' % self.kind]
            self.blacklist = self.expandList(userInput)
        self.logger.debug(5,'Converted %s blacklist: %s' %
                          (self.kind, ', '.join(self.blacklist)))

        self.whitelist = []
        if cfgParams.has_key('EDG.%s_white_list' % self.kind):
            userInput = cfgParams['EDG.%s_white_list' % self.kind]
            self.whitelist = self.expandList(userInput)
        self.logger.debug(5, 'Converted %s whitelist: %s' %
                          (self.kind, ', '.join(self.whitelist)))

        self.blacklist = sets.Set(self.blacklist)
        self.whitelist = sets.Set(self.whitelist)

    def expandList(self, userInput):
        """
        Contact SiteDB to expand lists like T2_US into lists of
        actual SE names and CE names.
        """

        userList = userInput.split(',')
        expandedList = []
        hadErrors = False
        for item in userList:
            item = item.strip()
            try:
                expandedItem = self.mapper(item)
            except Exception:
                # FIXME: WMCore SiteDB re-throws particular exception
                expandedItem = None
                hadErrors = True

            if expandedItem:
                expandedList.extend(expandedItem)
            else:
                expandedList.append(item)

        if hadErrors:
            self.logger.message("Problem connecting to SiteDB. " \
                                + "%s " % self.kind.upper() \
                                + "white/blacklist may be incomplete.")
            self.logger.message("List is %s" % expandedList)

        return expandedList

    def checkBlackList(self, sites, fileblocks=''):
        """
        Select sites that are not excluded by the user (via blacklist)

        The sites returned are the input sites minus the contents of the
        self.blacklist

        @param Sites: The sites which will be filtered
        @keyword fileblocks: The block this is used for; only used in a pretty
           debug message.
        @returns: The input sites minus the blacklist.
        """
        siteSet = sets.Set(sites)
        #print "Sites:",Sites
        blacklist = self.blacklist
        blacklist = sets.Set(self.matchList(siteSet, self.blacklist))
        #print "Black list:",blacklist
        goodSites = siteSet.difference(blacklist)
        #print "Good Sites:",goodSites,"\n"
        goodSites = list(goodSites)
        if not goodSites and fileblocks:
            msg = "No sites hosting the block %s after blackList" % fileblocks
            self.logger.debug(5, msg)
            self.logger.debug(5, "Proceeding without this block.\n")
        elif fileblocks:
            self.logger.debug(5, "Selected sites for block %s via blacklist " \
                "are %s.\n" % (', '.join(fileblocks), ', '.join(goodSites)))
        return goodSites

    def checkWhiteList(self, sites, fileblocks=''):
        """
        Select sites that are defined by the user (via white list).

        The sites returned are the intersection of the input sites and the
        contents of self.whitelist

        @param Sites: The sites which will be filtered
        @keyword fileblocks: The block this is applied for; only used for a
           pretty debug message
        @returns: The intersection of the input Sites and self.whitelist.
        """
        if not self.whitelist:
            return sites
        whitelist = self.whitelist
        whitelist = self.matchList(sites, self.whitelist)
        #print "White list:",whitelist
        siteSet = sets.Set(sites)
        goodSites = siteSet.intersection(whitelist)
        #print "Good Sites:",goodSites,"\n"
        goodSites = list(goodSites)
        if not goodSites and fileblocks:
            msg = "No sites hosting the block %s after whiteList" % fileblocks
            self.logger.debug(5, msg)
            self.logger.debug(5, "Proceeding without this block.\n")
        elif fileblocks:
            self.logger.debug(5, "Selected sites for block %s via whitelist "\
                " are %s.\n" % (', '.join(fileblocks), ', '.join(goodSites)))

        return goodSites

    def cleanForBlackWhiteList(self, destinations, isList=False):
        """
        Clean for black/white lists using parser.

        Take the input list and apply the blacklist, then the whitelist that
        the user specified.

        @param destinations: A list of all the input sites
        @keyword list: Set to True or the string 'list' to return a list
           object.  Set to False or the string '' to return a string object.
           The default is False.
        @returns: The list of all input sites, first filtered by the blacklist,
           then filtered by the whitelist.  If list=True, returns a list; if
           list=False, return a string.
        """
        if isList:
            return self.checkWhiteList(self.checkBlackList(destinations))
        else:
            return ','.join(self.checkWhiteList(self.checkBlackList( \
                destinations)))


    def matchList(self, names, siteList):
        """
        Filter a list of names against a comma-separated list of expressions.

        This uses the `match` function to do the heavy lifting

        @param names: A list of input names to filter
        @type names: list
        @param match_list: A comma-separated list of expressions
        @type siteList: str
        @returns: A list, filtered from `names`, of all entries which match an
          expression in siteList
        @rtype: list
        """
        results = []
        if isinstance(siteList, types.StringType):
            siteList = siteList.split(',')

        for expr in siteList:
            expr = expr.strip()
            matching = self.match(names, expr)
            if matching:
                results.extend(matching)
            else:
                results.append(expr)
        return results


    def match(self, names, expr):
        """
        Return all the entries in `names` which match `expr`

        First, try to apply wildcard-based filters, then look at substrings,
        then interpret expr as a regex.

        @param names: An input list of strings to match
        @param expr: A string expression to use for matching
        @returns: All entries in the list `names` which match `expr`
        """

        results = fnmatch.filter(names, expr)
        results.extend([i for i in names if i.find(expr) >= 0])
        try:
            regExp = re.compile(expr)
        except:
            regExp = None
        if not regExp:
            return results
        results.extend([i for i in names if regExp.search(i)])
        return results



class SEBlackWhiteListParser(BlackWhiteListParser):
    """
    Use the BlackWhiteListParser to filter out the possible list of SEs
    from the user's input; see the documentation for BlackWhiteListParser.
    """

    def __init__(self, cfgParams, logger=None):
        super(SEBlackWhiteListParser, self).__init__(cfgParams, logger)
        self.kind = 'se'
        self.mapper = self.siteDBAPI.cmsNametoSE
        self.configure(cfgParams)



class CEBlackWhiteListParser(BlackWhiteListParser):
    """
    Use the BlackWhiteListParser to filter out the possible list of CEs
    from the user's input; see the documentation for BlackWhiteListParser.
    """

    def __init__(self, cfgParams, logger=None):
        super(CEBlackWhiteListParser, self).__init__(cfgParams, logger)
        self.kind = 'ce'
        self.mapper = self.siteDBAPI.cmsNametoCE
        self.configure(cfgParams)
