#!/usr/bin/env python
"""
_LumiBased_t

Test lumi based splitting.
"""




import os
import threading
import logging
import unittest
import random

from WMCore.WMBS.File import File
from WMCore.WMBS.Fileset import Fileset
from WMCore.WMBS.Job import Job
from WMCore.WMBS.Subscription import Subscription
from WMCore.WMBS.Workflow import Workflow
from WMCore.DataStructs.Run import Run

from WMCore.DAOFactory import DAOFactory
from WMCore.WMFactory import WMFactory
from WMCore.JobSplitting.SplitterFactory import SplitterFactory
from WMCore.Services.UUID import makeUUID
from WMQuality.TestInitCouchApp import TestInitCouchApp as TestInit
from WMCore.ACDC.DataCollectionService import DataCollectionService
from WMCore.WMSpec.WMWorkload import newWorkload, WMWorkloadHelper

class LumiBasedTest(unittest.TestCase):
    """
    _EventBasedTest_

    Test event based job splitting.
    """

    def setUp(self):
        """
        _setUp_

        Create two subscriptions: One that contains a single file and one that
        contains multiple files.
        """


        
        self.testInit = TestInit(__file__)
        self.testInit.setLogging()
        self.testInit.setDatabaseConnection()
        #self.testInit.clearDatabase(modules = ['WMCore.WMBS'])
        self.testInit.setSchema(customModules = ["WMCore.WMBS"],
                                useDefault = False)
        self.testInit.setupCouch("wmcore-acdc-datacollectionsvc", "GroupUser", "ACDC")
        
        myThread = threading.currentThread()
        daofactory = DAOFactory(package = "WMCore.WMBS",
                                logger = myThread.logger,
                                dbinterface = myThread.dbi)

        locationAction = daofactory(classname = "Locations.New")
        locationAction.execute(siteName = 's1', seName = "somese.cern.ch")
        locationAction.execute(siteName = 's2', seName = "otherse.cern.ch")

        self.testWorkflow = Workflow(spec = "spec.xml", owner = "mnorman",
                                     name = "wf001", task="Test")
        self.testWorkflow.create()


        return

    def tearDown(self):
        """
        _tearDown_

        Nothing to do...
        """

        self.testInit.clearDatabase()
        self.testInit.tearDownCouch()        
        return


    def createSubscription(self, nFiles, lumisPerFile, twoSites = False, rand = False):
        """
        _createSubscription_
        
        Create a subscription for testing
        """

        baseName = makeUUID()

        testFileset = Fileset(name = baseName)
        testFileset.create()
        for i in range(nFiles):
            newFile = File(lfn = '%s_%i' % (baseName, i), size = 1000,
                           events = 100, locations = "somese.cern.ch")
            lumis = []
            for lumi in range(lumisPerFile):
                if rand:
                    lumis.append(random.randint(1000 * i, 1000 * (i + 1)))
                else:
                    lumis.append((100 * i) + lumi)
            newFile.addRun(Run(i, *lumis))
            newFile.create()
            testFileset.addFile(newFile)
        if twoSites:
            for i in range(nFiles):
                newFile = File(lfn = '%s_%i_2' % (baseName, i), size = 1000,
                               events = 100, locations = "otherse.cern.ch")
                lumis = []
                for lumi in range(lumisPerFile):
                    if rand:
                        lumis.append(random.randint(1000 * i, 1000 * (i + 1)))
                    else:
                        lumis.append((100 * i) + lumi)
                newFile.addRun(Run(i, *lumis))
                newFile.create()
                testFileset.addFile(newFile)
        testFileset.commit()


        testSubscription  = Subscription(fileset = testFileset,
                                         workflow = self.testWorkflow,
                                         split_algo = "LumiBased",
                                         type = "Processing")
        testSubscription.create()

        return testSubscription




    def testA_FileSplitting(self):
        """
        _FileSplitting_

        Test that things work if we split files between jobs
        """
        splitter = SplitterFactory()

        oneSetSubscription = self.createSubscription(nFiles = 10, lumisPerFile = 1)
        jobFactory = splitter(package = "WMCore.WMBS",
                              subscription = oneSetSubscription)


        jobGroups = jobFactory(lumis_per_job = 3,
                               split_files_between_job = True)
        self.assertEqual(len(jobGroups), 1)
        self.assertEqual(len(jobGroups[0].jobs), 10)
        for job in jobGroups[0].jobs:
            self.assertTrue(len(job['input_files']), 1)




        twoLumiFiles = self.createSubscription(nFiles = 5, lumisPerFile = 2)
        jobFactory = splitter(package = "WMCore.WMBS",
                              subscription = twoLumiFiles)
        jobGroups = jobFactory(lumis_per_job = 1,
                               split_files_between_job = True)
        self.assertEqual(len(jobGroups), 1)
        self.assertEqual(len(jobGroups[0].jobs), 10)
        for job in jobGroups[0].jobs:
            self.assertEqual(len(job['input_files']), 1)



        wholeLumiFiles = self.createSubscription(nFiles = 5, lumisPerFile = 3)
        jobFactory = splitter(package = "WMCore.WMBS",
                              subscription = wholeLumiFiles)
        jobGroups = jobFactory(lumis_per_job = 2,
                               split_files_between_job = True)
        self.assertEqual(len(jobGroups), 1)
        # 10 because we split on run boundaries
        self.assertEqual(len(jobGroups[0].jobs), 10)
        jobList = jobGroups[0].jobs
        for job in jobList:
            # Have should have one file, half two
            self.assertTrue(len(job['input_files']) in [1,2])


        mask0 = jobList[0]['mask'].getRunAndLumis()
        self.assertEqual(mask0, {0L: [[0L, 1L]]})
        mask1 = jobList[1]['mask'].getRunAndLumis()
        self.assertEqual(mask1, {0L: [[2L, 2L]]})
        mask2 = jobList[2]['mask'].getRunAndLumis()
        self.assertEqual(mask2, {1L: [[100L, 101L]]})
        mask3 = jobList[3]['mask'].getRunAndLumis()
        self.assertEqual(mask3, {1L: [[102L, 102L]]})

        j0 = Job(id = jobList[0]['id'])
        j0.loadData()
        self.assertEqual(j0['mask'].getRunAndLumis(), {0L: [[0L, 1L]]})

        # Do it with multiple sites
        twoSiteSubscription = self.createSubscription(nFiles = 5, lumisPerFile = 2, twoSites = True)
        jobFactory = splitter(package = "WMCore.WMBS",
                              subscription = twoSiteSubscription)
        jobGroups = jobFactory(lumis_per_job = 1,
                               split_files_between_job = True)
        self.assertEqual(len(jobGroups), 2)
        self.assertEqual(len(jobGroups[0].jobs), 10)
        for job in jobGroups[0].jobs:
            self.assertEqual(len(job['input_files']), 1)



    def testB_NoRunNoFileSplitting(self):
        """
        _NoRunNoFileSplitting_

        Test the splitting algorithm in the odder fringe
        cases that might be required.
        """
        splitter = SplitterFactory()
        testSubscription = self.createSubscription(nFiles = 5, lumisPerFile = 5, twoSites = False)
        jobFactory = splitter(package = "WMCore.WMBS",
                              subscription = testSubscription)

        jobGroups = jobFactory(lumis_per_job = 3,
                               split_files_between_job = False,
                               splitOnRun = False)

        self.assertEqual(len(jobGroups), 1)
        jobs = jobGroups[0].jobs
        self.assertEqual(len(jobs), 9)

        # The first job should have three lumis from one run
        # The second three lumis from two different runs
        self.assertEqual(jobs[0]['mask'].getRunAndLumis(), {0L: [[0L, 2L]]})
        self.assertEqual(jobs[1]['mask'].getRunAndLumis(), {0L: [[3L, 4L]], 1L: [[100L, 100L]]})


        # And it should still be the same when you load it out of the database
        j1 = Job(id = jobs[1]['id'])
        j1.loadData()
        self.assertEqual(j1['mask'].getRunAndLumis(), {0L: [[3L, 4L]], 1L: [[100L, 100L]]})

        # Assert that this works differently with file splitting on and run splitting on
        testSubscription = self.createSubscription(nFiles = 5, lumisPerFile = 5, twoSites = False)
        jobFactory = splitter(package = "WMCore.WMBS",
                              subscription = testSubscription)
        jobGroups = jobFactory(lumis_per_job = 3,
                               split_files_between_job = True,
                               splitOnRun = True)
        self.assertEqual(len(jobGroups), 1)
        jobs = jobGroups[0].jobs
        self.assertEqual(len(jobs), 10)
        
        # In this case it should slice things up so that each job only has one run
        # in it.
        self.assertEqual(jobs[0]['mask'].getRunAndLumis(), {0L: [[0L, 2L]]})
        self.assertEqual(jobs[1]['mask'].getRunAndLumis(), {0L: [[3L, 4L]]})
        return

    def createTestWorkload(self):
        """
        _createTestWorkload_

        """
        workload = newWorkload("ACDCTest")        
        reco = workload.newTask("reco")
        skim1 = reco.addTask("skim1")
        workload.setOwnerDetails("evansde77", "DMWM")

        # first task uses the input dataset
        reco.addInputDataset(primary = "PRIMARY", processed = "processed-v1", tier = "TIER1")
        cmsRunReco = reco.makeStep("cmsRun1")
        cmsRunReco.setStepType("CMSSW")
        reco.applyTemplates()
        cmsRunRecoHelper = cmsRunReco.getTypeHelper()
        cmsRunRecoHelper.addOutputModule("outputRECO",
                                        primaryDataset = "PRIMARY",
                                        processedDataset = "processed-v2",
                                        dataTier = "TIER2",
                                        lfnBase = "/store/dunkindonuts",
                                        mergedLFNBase = "/store/kfc")
        # second step uses an input reference
        cmsRunSkim = skim1.makeStep("cmsRun2")
        cmsRunSkim.setStepType("CMSSW")
        skim1.applyTemplates()        
        skim1.setInputReference(cmsRunReco, outputModule = "outputRECO")

        return workload


    def testC_ACDCTest(self):
        """
        _ACDCTest_

        Test whether we can get a goodRunList out of ACDC
        and process it correctly.
        """
        dcs = DataCollectionService(url = self.testInit.couchUrl, database = self.testInit.couchDbName)        

        workload = self.createTestWorkload()
        collection = dcs.createCollection(workload)

        def getJob(workload):
            job = Job()
            job["task"] = workload.getTask("reco").getPathName()
            job["workflow"] = workload.name()
            job["location"] = "T1_US_FNAL"
            return job

        testFileA = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileA.addRun(Run(1, 1, 2))
        testFileA.create()
        testFileB = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileB.addRun(Run(1, 3))
        testFileB.create()
        testJobA = getJob(workload)
        testJobA.addFile(testFileA)
        testJobA.addFile(testFileB)

        testFileC = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileC.addRun(Run(1, 4, 6))
        testFileC.create()
        testJobB = getJob(workload)
        testJobB.addFile(testFileC)
        
        testFileD = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileD.addRun(Run(1, 7))
        testFileD.create()
        testJobC = getJob(workload)
        testJobC.addFile(testFileD)
                         
        testFileE = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileE.addRun(Run(1, 11, 12))
        testFileE.create()
        testJobD = getJob(workload)
        testJobD.addFile(testFileE)

        testFileF = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileF.addRun(Run(2, 5, 6, 7))
        testFileF.create()
        testJobE = getJob(workload)
        testJobE.addFile(testFileF)

        testFileG = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileG.addRun(Run(2, 10, 11, 12))
        testFileG.create()
        testJobF = getJob(workload)
        testJobF.addFile(testFileG)

        testFileH = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileH.addRun(Run(2, 15))
        testFileH.create()
        testJobG = getJob(workload)
        testJobG.addFile(testFileH)

        testFileI = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileI.addRun(Run(3, 20))
        testFileI.create()
        testJobH = getJob(workload)
        testJobH.addFile(testFileI)

        testFileJ = File(lfn = makeUUID(), size = 1024, events = 1024, locations = "somese.cern.ch")
        testFileJ.addRun(Run(1, 9))
        testFileJ.create()
        testJobI = getJob(workload)
        testJobI.addFile(testFileJ)

        #dcs.failedJobs([testJobA, testJobB, testJobC, testJobD, testJobE,
        #                testJobF, testJobG, testJobH, testJobI])

        dcs.failedJobs([testJobA, testJobD, testJobH])

        baseName = makeUUID()

        testFileset = Fileset(name = baseName)
        testFileset.create()
        testFileset.addFile(testFileA)
        testFileset.addFile(testFileB)
        testFileset.addFile(testFileC)
        testFileset.addFile(testFileD)
        testFileset.addFile(testFileE)
        testFileset.addFile(testFileF)
        testFileset.addFile(testFileG)
        testFileset.addFile(testFileH)
        testFileset.addFile(testFileI)
        testFileset.addFile(testFileJ)
        testFileset.commit()

        testSubscription  = Subscription(fileset = testFileset,
                                         workflow = self.testWorkflow,
                                         split_algo = "LumiBased",
                                         type = "Processing")
        testSubscription.create()

        splitter = SplitterFactory()
        jobFactory = splitter(package = "WMCore.WMBS",
                              subscription = testSubscription)

        jobGroups = jobFactory(lumis_per_job = 100,
                               split_files_between_job = False,
                               splitOnRun = True,
                               goodLumiListURL = collection["collection_id"],
                               task = workload.getTask("reco").getPathName(),
                               couchURL = self.testInit.couchUrl,
                               couchDB = self.testInit.couchDbName)


        self.assertEqual(jobGroups[0].jobs[0]['mask'].getRunAndLumis(), {1L: [[1L, 2L], [3L, 3L], [11L, 12L]]})
        self.assertEqual(jobGroups[0].jobs[1]['mask'].getRunAndLumis(), {3L: [[20L, 20L]]})

            
        
        


if __name__ == '__main__':
    unittest.main()
