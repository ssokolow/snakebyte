#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test Suite for Queue code for SnakeByte FServe

:todo: Get ``coverage.py``'s branch coverage working and make sure there are
       no branches I forgot to test.
"""

__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.1"
__license__ = "GNU GPL 3.0 or later"

import heapq, logging, string, unittest
log = logging.getLogger(__name__)

from collections import OrderedDict

from queue import FairQueue

class MockUser(object):
    """A simple placeholder for a real user in the queue-testing process."""
    def __init__(self, bucket_id, desires):
        self.bucket_id = bucket_id

        self.goal = desires
        self.todo = desires[:]
        self.done = []

    def request(self):
        if self.todo:
            return self.todo.pop(0)
        else:
            return None

    def received(self, item):
        self.done.append(item)

    def is_satisfied(self):
        return self.done == self.goal

    def as_fresh_tuple(self):
        """Return a tuple suitable for populating queues when
        gathered in an iterable and fed to __init_.

        The "fresh" indicates that this ignores `request` and `received`.
        """
        return self.bucket_id, self.goal[:]

    #TODO: Still need to decide how to implement testing of ordering

class BaseTestQueue(unittest.TestCase):
    """Code common to tests which start with empty or populated queues."""
    chars = string.digits + string.ascii_letters #: For building filenames
    files = ['file%s' % chars[x] for x in range(0,6)]
    priority_cb = None
    #priority_cb = staticmethod(lambda x:5)
    #TODO: Test with constant, monotonic increase, variable increase, and pseudo-random

    def setUp(self):
        super(BaseTestQueue, self).setUp()

        self.users = OrderedDict()
        for i in range (0,2):
            for j in range(0,5):
                user = MockUser(('network%d' % i, 'user%d' % j), self.files)
                self.users[user.bucket_id] = user

    def tearDown(self):
        self._check_invariants()

    def _check_invariants(self, target_count=None, queue=None):
        """Tests which should pass after every change to the queue."""
        queue = queue or self.queue

        self.assertEqual(len(queue._buckets), len(queue._subqueues),
                "There should be exactly one subqueue per entry in the bucket heap")
        self.assertTrue(all(queue._subqueues.values()),
                "Subqueues should be removed when their last item is retrieved")

        if target_count is not None:
            self.assertEqual(len(queue._buckets), target_count,
                    "Bucket heap should gain one (and only one) entry per bucket")
            self.assertEqual(len(queue._subqueues), target_count,
                    "Subqueues dict should gain one (and only one) entry per bucket")

        test_heap = self.queue._buckets[:]
        heapq.heapify(test_heap)
        self.assertEqual(self.queue._buckets, test_heap,
                "Previous operation may have broken the heap invariant!")

    def _check_equivalence(self, other):
        """Tests which should pass once all requests have been inserted."""
        users_in_heap = [x[1] for x in sorted(self.queue._buckets)]

        if isinstance(other, FairQueue):
            users_in_other_heap = [x[1] for x in sorted(other._buckets)]
            self.assertEquals(users_in_heap, users_in_other_heap,
                    "Heap ordering not equivalent")

            other = other._subqueues
        else:
            other = OrderedDict((x, other[x].goal) for x in other)

        for user in other:
            self.assertIn(user, users_in_heap,
                    "One or more buckets missing from the heap")
            self.assertIn(user, self.queue._subqueues,
                    "One or more buckets missing from the subqueue dict")
            self.assertEqual(other[user], self.queue._subqueues[user],
                    "Must not drop or reorder requests within the same bucket")

        for user in users_in_heap:
            self.assertIn(user, other, "Queue has heap entries not present in other")
        for user in self.queue._subqueues:
            self.assertIn(user, other, "Queue has subqueues not present in other")

    def _get_init_data(self):
        return [x.as_fresh_tuple() for x in self.users.values()]

#TODO: Use something like a metaclass or closure to run this stuff once per priority_cb
class TestEmptyQueue(BaseTestQueue):
    def setUp(self):
        super(TestEmptyQueue, self).setUp()
        self.queue = FairQueue(priority_cb=self.priority_cb)

        self.assertFalse(self.queue._buckets, "Queue did not start empty")
        self.assertFalse(self.queue._subqueues, "Queue did not start empty")

    def test_initial_data(self):
        """Test setting up a queue with initial data"""
        data = self._get_init_data()
        for dtype in (lambda x:x, list, dict, OrderedDict):
            self.queue = FairQueue(
                    contents=dtype(data),
                    priority_cb=self.priority_cb)

            self.assertTrue(all(x for x in self.queue._subqueues.values()),
                    "Queue was initialized with empty subqueues")

            self._check_invariants(len(self.users))
            self._check_equivalence(self.users)

        # Check merging behaviour
        self.queue = FairQueue(
                contents=[(1,[1,2]),(3,[3,4]),(1,[3,6])],
                priority_cb=self.priority_cb)
        self._check_invariants(2)
        self._check_equivalence(FairQueue(contents=[(1,[1,2,3,6]),(3,[3,4])]))

    def test_invalid_get(self):
        """Test reaction to `FairQueue.get` on empty queue"""
        self.assertRaises(IndexError, self.queue.get)
        self.assertRaises(KeyError, self.queue.get, ('test', 'tuple', 'with', '%r'))

    def test_invalid_get_bucket(self):
        """Test reaction to `FairQueue.get_bucket` on a nonexistant ID"""
        self.assertRaises(KeyError, self.queue.get_bucket, 'nonexistant')
        self.assertRaises(KeyError, self.queue.get_bucket, ('test', 'tuple'))

    def test_invalid_load(self):
        """Test reaction to invalid `FairQueue.load` input"""
        self.assertRaises(TypeError, FairQueue.load, ({}, {}))
        self.assertRaises(TypeError, FairQueue.load, ([], []))

    def test_invalid_put(self):
        """Test reaction to unhashable ``bucket_id``"""
        self.assertRaises(TypeError, self.queue.put, {}, None)
        self.assertFalse(self.queue._buckets,
                "Refusal of invalid keys must not alter the bucket heap")
        self.assertFalse(self.queue._subqueues,
                "Refusal of invalid keys must not alter the subqueue dict")

        # Now make sure it doesn't bother existing content
        self.queue.put(1,2)
        _b, _q = self.queue._buckets[:], self.queue._subqueues.copy()

        self.assertRaises(TypeError, self.queue.put, {}, None)
        self.assertEqual(_b, self.queue._buckets,
                "Refusal of invalid keys must not alter the bucket heap")
        self.assertEqual(_q, self.queue._subqueues,
                "Refusal of invalid keys must not alter the subqueue dict")


    def test_put(self):
        """Test behaviour of valid `FairQueue.put` calls"""
        target_count = 0
        for user in self.users.values():
            self._check_invariants(target_count)

            #TODO: Need to test with mock time.time() in case of low-resolution timers.
            for entry in iter(user.request, None):
                self.queue.put(user.bucket_id, entry)

            target_count += 1
        self._check_equivalence(self.users)

    def test_populate_equivalence(self):
        """Test that `FairQueue.__init__` and `FairQueue.put` affect order similarly"""
        populated_queue = FairQueue(
            contents=self._get_init_data(),
            priority_cb=self.priority_cb)

        for user in self.users.values():
            for entry in iter(user.request, None):
                self.queue.put(user.bucket_id, entry)

        self._check_equivalence(populated_queue)

class TestPopulatedQueue(BaseTestQueue):
    def setUp(self):
        super(TestPopulatedQueue, self).setUp()
        self.queue = FairQueue(priority_cb=self.priority_cb,
            contents=self._get_init_data())

        self._check_invariants()
        self.assertTrue(self.queue._buckets, "Queue started empty")
        self.assertTrue(self.queue._subqueues, "Queue started empty")
        self.assertTrue(all(x for x in self.queue._subqueues.values()),
                "Queue started with empty subqueues")

    def test_dump_load_symmetry(self):
        """Test symmetry of `FairQueue.dump` and `FairQueue.load`"""
        dump = self.queue.dump()
        newQueue = self.queue.load(dump)
        #TODO: Also need to test load's **kwargs

        self._check_equivalence(newQueue)
        #TODO: Also needs an ordering check

    def test_get(self):
        """Test behaviour of valid `FairQueue.get` calls without ``bucket_id``"""
        #TODO: Maybe the queue should support being iterable
        try:
            for bucket_id, entry in iter(self.queue.get, None):
                self._check_invariants()
                self.users[bucket_id].received(entry)
        except IndexError:
            pass #TODO: Figure out a better way to determine end of queue

        unsatisfied = [x for x in self.users.values() if not x.is_satisfied()]
        self.assertFalse(unsatisfied,
                'Not all users received their files:\n\t%s' %
                '\n\t'.join('%s: %s, %s' % (x.bucket_id, x.goal, x.done)
                    for x in unsatisfied))
        #TODO: Also need to test ordering
        #TODO: Also need to test that the effect of removing and adding
        #      user always results in an equal or newer timestamp.
        #TODO: Decide how to ensure that mutating the list to emptiness
        #      can't wedge the queue.

    def test_get_with_id(self):
        """Test behaviour of `FairQueue.get` calls with ``bucket_id`` parameter"""
        self.assertRaises(KeyError, self.queue.get, 'nonexistant')

        for user in self.users.values():
            retrieved = []
            try:
                while True:
                    retrieved.append(self.queue.get(bucket_id=user.bucket_id))
            except KeyError:
                self.assertFalse([x for x in retrieved if x[0] != user.bucket_id])
                self.assertEqual([x[1] for x in retrieved], user.goal)

    def test_get_bucket(self):
        """Test `FairQueue.get_bucket`"""
        for user in self.users.values():
            bucket = self.queue.get_bucket(user.bucket_id)
            self._check_invariants()
            self.assertEqual(bucket, user.goal)

            bucket[0], bucket[1] = bucket[1], bucket[0]
            self.assertEqual(bucket, self.queue.get_bucket(user.bucket_id),
                    "Mutations to the list returned by get_bucket() must take effect.")

        # Just to make sure it doesn't behave differently than an empty queue
        self.assertRaises(KeyError, self.queue.get_bucket, 'nonexistant')

    def test_invalid_get(self):
        """Test reaction to `FairQueue.get` on populated queue"""
        self.assertRaises(KeyError, self.queue.get, 'nonexistant')
