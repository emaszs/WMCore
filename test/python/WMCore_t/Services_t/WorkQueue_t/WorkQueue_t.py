#!/usr/bin/env python
from __future__ import print_function, division
import unittest
import time

from WMCore.WorkQueue.WorkQueue import globalQueue
from WMCore.WorkQueue.WorkQueue import localQueue
from WMCore.Services.WorkQueue.WorkQueue import WorkQueue as WorkQueueDS
from WMCore.Services.WorkQueue.WorkQueue import convertWQElementsStatusToWFStatus
from WMQuality.Emulators.WMSpecGenerator.WMSpecGenerator import WMSpecGenerator
from WMQuality.Emulators.EmulatedUnitTestCase import EmulatedUnitTestCase
from WMQuality.TestInitCouchApp import TestInitCouchApp


class WorkQueueTest(EmulatedUnitTestCase):
    """
    Test WorkQueue Service client
    It will start WorkQueue RESTService
    Server DB sets from environment variable.
    Client DB sets from environment variable.

    This checks whether DS call makes without error and return the results.
    Not the correctness of functions. That will be tested in different module.
    """

    def setUp(self):
        """
        _setUp_
        """
        super(WorkQueueTest, self).setUp()

        self.specGenerator = WMSpecGenerator("WMSpecs")
        # self.configFile = EmulatorSetup.setupWMAgentConfig()
        self.schema = []
        self.couchApps = ["WorkQueue"]
        self.testInit = TestInitCouchApp('WorkQueueServiceTest')
        self.testInit.setLogging()
        self.testInit.setDatabaseConnection()
        self.testInit.setSchema(customModules=self.schema,
                                useDefault=False)
        self.testInit.setupCouch('workqueue_t', *self.couchApps)
        self.testInit.setupCouch('workqueue_t_inbox', *self.couchApps)
        self.testInit.setupCouch('local_workqueue_t', *self.couchApps)
        self.testInit.setupCouch('local_workqueue_t_inbox', *self.couchApps)
        self.testInit.generateWorkDir()
        return

    def tearDown(self):
        """
        _tearDown_

        Drop all the WMBS tables.
        """
        self.testInit.tearDownCouch()
        self.specGenerator.removeSpecs()
        super(WorkQueueTest, self).tearDown()

    def testWorkQueueService(self):
        # test getWork
        specName = "RerecoSpec"
        specUrl = self.specGenerator.createReRecoSpec(specName, "file")
        globalQ = globalQueue(DbName='workqueue_t',
                              QueueURL=self.testInit.couchUrl,
                              UnittestFlag=True)
        self.assertTrue(globalQ.queueWork(specUrl, specName, "teamA") > 0)

        wqApi = WorkQueueDS(self.testInit.couchUrl, 'workqueue_t')
        # overwrite default - can't test with stale view
        wqApi.defaultOptions = {'reduce': True, 'group': True}
        # This only checks minimum client call not exactly correctness of return
        # values.
        self.assertEqual(wqApi.getTopLevelJobsByRequest(),
                         [{'total_jobs': 334, 'request_name': specName}])
        # work still available, so no childQueue
        self.assertEqual(wqApi.getChildQueuesAndStatus().keys(), [None])
        result = wqApi.getElementsCountAndJobsByWorkflow()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[specName]['Available']['Jobs'], 334)

        self.assertEqual(wqApi.getChildQueuesAndPriority()[None].keys(), [8000])
        self.assertEqual(wqApi.getWMBSUrl(), [])
        self.assertEqual(wqApi.getWMBSUrlByRequest(), [])

    def testUpdatePriorityService(self):
        """
        _testUpdatePriorityService_

        Check that we can update the priority correctly also
        check the available workflows feature
        """
        specName = "RerecoSpec"
        specUrl = self.specGenerator.createReRecoSpec(specName, "file", SiteWhitelist=["T2_XX_SiteA"])
        globalQ = globalQueue(DbName='workqueue_t',
                              QueueURL=self.testInit.couchUrl,
                              UnittestFlag=True)
        localQ = localQueue(DbName='local_workqueue_t',
                            QueueURL=self.testInit.couchUrl,
                            CacheDir=self.testInit.testDir,
                            ParentQueueCouchUrl='%s/workqueue_t' % self.testInit.couchUrl,
                            ParentQueueInboxCouchDBName='workqueue_t_inbox'
                            )
        # Try a full chain of priority update and propagation
        self.assertTrue(globalQ.queueWork(specUrl, "RerecoSpec", "teamA") > 0)
        globalApi = WorkQueueDS(self.testInit.couchUrl, 'workqueue_t')
        # overwrite default - can't test with stale view
        globalApi.defaultOptions = {'reduce': True, 'group': True}
        globalApi.updatePriority(specName, 100)
        self.assertEqual(globalQ.backend.getWMSpec(specName).priority(), 100)
        storedElements = globalQ.backend.getElementsForWorkflow(specName)
        for element in storedElements:
            self.assertEqual(element['Priority'], 100)
        numWorks = localQ.pullWork({'T2_XX_SiteA': 10})
        self.assertTrue(numWorks > 0)
        # replicate from GQ to LQ manually
        localQ.backend.pullFromParent(continuous=False)
        # wait until replication is done
        time.sleep(2)

        localQ.processInboundWork(continuous=False)
        storedElements = localQ.backend.getElementsForWorkflow(specName)
        for element in storedElements:
            self.assertEqual(element['Priority'], 100)
        localApi = WorkQueueDS(self.testInit.couchUrl, 'local_workqueue_t')
        # overwrite default - can't test with stale view
        localApi.defaultOptions = {'reduce': True, 'group': True}
        localApi.updatePriority(specName, 500)
        self.assertEqual(localQ.backend.getWMSpec(specName).priority(), 500)
        storedElements = localQ.backend.getElementsForWorkflow(specName)
        for element in storedElements:
            self.assertEqual(element['Priority'], 500)
        availableWF = localApi.getAvailableWorkflows()
        self.assertEqual(availableWF, set([(specName, 500)]))
        # Attempt to update an inexistent workflow in the queue
        try:
            globalApi.updatePriority('NotExistent', 2)
        except Exception as ex:
            self.fail('No exception should be raised.: %s' % str(ex))

    def testCompletedWorkflow(self):
        # test getWork
        specName = "RerecoSpec"
        specUrl = self.specGenerator.createReRecoSpec(specName, "file")
        globalQ = globalQueue(DbName='workqueue_t',
                              QueueURL=self.testInit.couchUrl,
                              UnittestFlag=True)
        self.assertTrue(globalQ.queueWork(specUrl, specName, "teamA") > 0)

        wqApi = WorkQueueDS(self.testInit.couchUrl, 'workqueue_t')
        # overwrite default - can't test with stale view
        wqApi.defaultOptions = {'reduce': True, 'group': True}
        # This only checks minimum client call not exactly correctness of return
        # values.
        self.assertEqual(wqApi.getTopLevelJobsByRequest(),
                         [{'total_jobs': 334, 'request_name': specName}])
        results = wqApi.getJobsByStatusAndPriority()
        self.assertEqual(results.keys(), ['Available'])
        self.assertEqual(results['Available'].keys(), [8000])
        self.assertTrue(results['Available'][8000]['sum'], 334)
        result = wqApi.getElementsCountAndJobsByWorkflow()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[specName]['Available']['Jobs'], 334)
        data = wqApi.db.loadView('WorkQueue', 'elementsDetailByWorkflowAndStatus',
                                 {'startkey': [specName], 'endkey': [specName, {}],
                                  'reduce': False})
        elements = [x['id'] for x in data.get('rows', [])]
        wqApi.updateElements(*elements, Status='Canceled')
        # load this view once again to make sure it will be updated in the next assert..
        data = wqApi.db.loadView('WorkQueue', 'elementsDetailByWorkflowAndStatus',
                                 {'startkey': [specName], 'endkey': [specName, {}],
                                  'reduce': False})
        self.assertEqual(len(wqApi.getCompletedWorkflow(stale=False)), 1)
        self.assertEqual(wqApi.getJobsByStatusAndPriority().keys(), ['Canceled'])

    def testConvertWQElementsStatusToWFStatus(self):
        """
        _testConvertWQElementsStatusToWFStatus_

        Check that a set of all the workqueue element status in a request
        properly maps to a single state to trigger the ReqMgr request transition.
        """
        # workflows acquired by global_workqueue (nothing acquired by agents so far)
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Available"])), "acquired")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Negotiating"])), "acquired")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Available", "Negotiating"])), "acquired")

        # workflows not completely acquired yet by the agents
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Acquired"])), "running-open")

        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Available", "Negotiating", "Acquired"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Available", "Negotiating", "Acquired", "Running"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Available", "Negotiating", "Acquired", "Running", "Done"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Available", "Negotiating", "Acquired", "Running", "Done", "CancelRequested"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Available", "Negotiating", "Acquired", "Running", "Done", "CancelRequested", "Canceled"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Negotiating", "Acquired"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Negotiating", "Acquired", "Running"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Negotiating", "Acquired", "Running", "Done"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Negotiating", "Acquired", "Running", "Done", "CancelRequested"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Negotiating", "Acquired", "Running", "Done", "CancelRequested", "Canceled"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Acquired", "Running"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Acquired", "Running", "Done"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Acquired", "Running", "Done", "CancelRequested"])), "running-open")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Acquired", "Running", "Done", "CancelRequested", "Canceled"])), "running-open")

        # workflows completely acquired by the agents
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Running"])), "running-closed")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Running", "Done"])), "running-closed")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Running", "Done", "CancelRequested"])), "running-closed")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Running", "Done", "CancelRequested", "Canceled"])), "running-closed")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Running", "Done", "Canceled"])), "running-closed")

        # workflows completed/aborted/force-completed, thus existent elements
        #  but no more active workqueue elements in the system
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Done"])), "completed")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Canceled"])), "completed")
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Done", "Canceled"])), "completed")

        # workflows failed
        self.assertEqual(convertWQElementsStatusToWFStatus(set(["Failed"])), "failed")

        # workflows in a temporary state, nothing to do with them yet
        self.assertIsNone(convertWQElementsStatusToWFStatus(set(["Done", "CancelRequested"])))
        self.assertIsNone(convertWQElementsStatusToWFStatus(set(["CancelRequested"])))


if __name__ == '__main__':
    unittest.main()
