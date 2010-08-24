#!/usr/bin/env python
"""
_EventBased_

Event based splitting algorithm that will chop a fileset into
a set of jobs based on event counts
"""

__revision__ = "$Id: EventBased.py,v 1.8 2009/03/03 09:48:24 gowdy Exp $"
__version__  = "$Revision: 1.8 $"

from sets import Set

from WMCore.JobSplitting.JobFactory import JobFactory
from WMCore.Services.UUID import makeUUID

class EventBased(JobFactory):
    """
    Split jobs by number of events
    """
    def algorithm(self, groupInstance = None, jobInstance = None, *args,
                  **kwargs):
        """
        _algorithm_

        An event base splitting algorithm.  All available files are split into a
        set number of events per job.  
        """
       
        #  //
        # // Resulting job set (shouldnt this be a JobGroup??)
        #//
        jobs = Set()

        #  //
        # // get the fileset
        #//
        fileset = self.subscription.availableFiles()

        #  //
        # // get the event total
        #//
        eventsPerJob = kwargs['events_per_job']
        carryOver = 0

        baseName = makeUUID()

        for f in fileset:
            eventsInFile = f['events']

            currentEvent = 0
            while currentEvent < eventsInFile:
                currentJob = jobInstance(name = '%s-%s' % (baseName, len(jobs) + 1))
                currentJob.addFile(f)
                currentJob.mask.setMaxAndSkipEvents(eventsPerJob, currentEvent)
                jobs.add(currentJob)
                currentEvent += eventsPerJob

        jobGroup = groupInstance(subscription = self.subscription)
        jobGroup.add(jobs)
        jobGroup.commit()
        jobGroup.recordAcquire(list(jobs))

        return [jobGroup]
