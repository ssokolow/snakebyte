#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test Suite for Queue code for SnakeByte FServe"""

__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 3.0 or later"
__docformat__ = "restructuredtext en"

import heapq, logging, string, sys
log = logging.getLogger(__name__)

if sys.version_info[0] == 2 and sys.version_info[1] < 7:  # pragma: no cover
    import unittest2 as unittest
    unittest  # Silence erroneous PyFlakes warning
else:                                                     # pragma: no cover
    import unittest

try:                                                      # pragma: no cover
    from collections import OrderedDict
    OrderedDict  # Silence erroneous PyFlakes warning
except ImportError:                                       # pragma: no cover
    from ordereddict import OrderedDict

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

    def __iter__(self):
        """Used for generating a tuple suitable for populating queues when
        gathered in an iterable and fed to __init_.

        The "fresh" indicates that this ignores `request` and `received`.
        """
        yield self.bucket_id
        yield self.goal[:]

    #TODO: Still need to decide how to implement testing of ordering fairness

class BaseTestQueue(unittest.TestCase):
    """Code common to all `FairQueue` tests."""
    nonexistant_keys = ('nonexistant key', ('nonexistant', 'key'))
    priority_cb = None
    #priority_cb = staticmethod(lambda x:5)
    #TODO: Test with constant, monotonic increase, variable increase, etc.

    chars = string.digits + string.ascii_letters  #: For building filenames
    files = ['file%s' % chars[x] for x in range(0, 6)]
    uids  = [('network%d' % i, 'user%d' % j)
            for i in range(0, 2) for j in range(0, 5)]

    # Add False-evaluating, non-None keys for robustness testing
    uids += [False, 0]

    def setUp(self):
        super(BaseTestQueue, self).setUp()

        self.users = OrderedDict()
        for uid in self.uids:
            user = MockUser(uid, self.files)
            self.users[user.bucket_id] = user

        self.assertIn(0, self.users, "Mock user setup failed: 0")
        self.assertIn(False, self.users, "Mock user setup failed: False")

    def tearDown(self):
        self._check_invariants()

    def _check_invariants(self, target_count=None, queue=None):
        """Tests which should pass after every change to the queue.

        :Parameters:
         - `target_count` If provided, also verify bucket counts.
        """
        queue = queue or self.queue

        self.assertEqual(len(queue._buckets), len(queue._subqueues),
                "There should be exactly one subqueue per entry in the heap")
        self.assertTrue(all(queue._subqueues.values()),
            "Empty subqueues should expire immediately for maximum fairness")

        if target_count is not None:
            self.assertEqual(len(queue._buckets), target_count,
                    "Bucket heap should gain exactly one entry per bucket")
            self.assertEqual(len(queue._subqueues), target_count,
                    "Subqueues dict should gain exactly one entry per bucket")

        test_heap = self.queue._buckets[:]
        heapq.heapify(test_heap)
        self.assertEqual(self.queue._buckets, test_heap,
                "Previous operation may have broken the heap invariant!")

    def _check_equivalence(self, other):
        """Tests which should pass once all requests have been inserted."""
        users_in_heap = [x[1] for x in sorted(self.queue._buckets)]

        if isinstance(other, FairQueue):
            self.assertEquals(len(self.queue), len(other))
            self.assertEquals(bool(self.queue), bool(other))

            users_in_other_heap = [x[1] for x in sorted(other._buckets)]
            self.assertEquals(users_in_heap, users_in_other_heap,
                    "Heap ordering not equivalent")
        else:
            other = OrderedDict((x, other[x].goal) for x in other)

        for user in other:
            self.assertIn(user, users_in_heap,
                    "One or more buckets missing from the heap")
            self.assertIn(user, self.queue,
                    "One or more buckets missing from the subqueue dict")
            self.assertEqual(other[user], self.queue[user],
                    "Must not drop or reorder requests within the same bucket")

        for user in users_in_heap:
            self.assertIn(user, other, "Queue has heap entries not in other")
        for user in self.queue._subqueues:
            self.assertIn(user, other, "Queue has subqueues not in other")

class TestEmptyQueue(BaseTestQueue):
    """Tests which start with an empty queue"""
    def setUp(self):
        super(TestEmptyQueue, self).setUp()
        self.queue = FairQueue(priority_cb=self.priority_cb)

        self.assertFalse(self.queue, "Queue did not initially evaluate False")
        self.assertEqual(len(self.queue), 0, "Queue began with nonzero length")
        self.assertFalse(self.queue._buckets, "Queue did not start empty")
        self.assertFalse(self.queue._subqueues, "Queue did not start empty")

    def test_initial_data(self):
        """Test setting up a queue with initial data"""
        data = self.users.values()
        for dtype in (lambda x: x, list, dict, OrderedDict):
            self.queue = FairQueue(
                    contents=dtype(data),
                    priority_cb=self.priority_cb)

            self.assertTrue(all(x for x in self.queue._subqueues.values()),
                    "Queue was initialized with empty subqueues")

            self._check_invariants(len(self.users))
            self._check_equivalence(self.users)

        # Check merging behaviour
        self.queue = FairQueue(
            contents=[(1, [1, 2]), (3, [3, 4]), (1, [3, 6])],
            priority_cb=self.priority_cb)
        self._check_invariants(2)
        self._check_equivalence(FairQueue(
            contents=[(1, [1, 2, 3, 6]), (3, [3, 4])]))

    def test_invalid_pop(self):
        """Test reaction to `FairQueue.pop` on empty queue"""
        self.assertRaises(IndexError, self.queue.pop)
        for key in self.nonexistant_keys:
            self.assertRaises(KeyError, self.queue.pop, key)

    def test_invalid_getitem(self):
        """Test reaction to `FairQueue.__getitem__` on a nonexistant ID"""
        for key in self.nonexistant_keys:
            self.assertRaises(KeyError, self.queue.__getitem__, key)

    def test_invalid_load(self):
        """Test reaction to invalid `FairQueue.load` input"""
        self.assertRaises(TypeError, FairQueue.load, ({}, {}))
        self.assertRaises(TypeError, FairQueue.load, ([], []))

    def test_invalid_push(self):
        """Test reaction to unhashable ``key`` in `FairQueue.push`"""
        self.assertRaises(TypeError, self.queue.push, {}, None)
        self.assertFalse(self.queue._buckets,
                "Refusal of invalid keys must not alter the bucket heap")
        self.assertFalse(self.queue._subqueues,
                "Refusal of invalid keys must not alter the subqueue dict")

        # Now make sure it doesn't bother existing content
        self.queue.push(1, 2)
        _b, _q = self.queue._buckets[:], self.queue._subqueues.copy()

        self.assertRaises(TypeError, self.queue.push, {}, None)
        self.assertEqual(_b, self.queue._buckets,
                "Refusal of invalid keys must not alter the bucket heap")
        self.assertEqual(_q, self.queue._subqueues,
                "Refusal of invalid keys must not alter the subqueue dict")

    def test_push(self):
        """Test behaviour of valid `FairQueue.push` calls"""
        target_count = 0
        for user in self.users.values():
            self._check_invariants(target_count)

            #TODO: Test with mock time.time() in case of low-resolution timers.
            for entry in iter(user.request, None):
                before = len(self.queue)
                self.queue.push(user.bucket_id, entry)
                self.assertEquals(before + 1, len(self.queue))

            target_count += 1
        self._check_equivalence(self.users)

    def test_populate_equivalence(self):
        """Test that `FairQueue.__init__` and `FairQueue.push` order equally"""
        populated_queue = FairQueue(
            contents=self.users.values(),
            priority_cb=self.priority_cb)

        for user in self.users.values():
            for entry in iter(user.request, None):
                self.queue.push(user.bucket_id, entry)

        self._check_equivalence(populated_queue)

class TestPopulatedQueue(BaseTestQueue):
    """Tests which start with a populated queue"""
    def setUp(self):
        super(TestPopulatedQueue, self).setUp()
        self.queue = FairQueue(priority_cb=self.priority_cb,
            contents=self.users.values())

        self._check_invariants()
        self.assertTrue(self.queue, "Queue did not start out evaluating True")
        self.assertTrue(len(self.queue), "Queue started out with zero length")
        self.assertTrue(self.queue._buckets, "Queue started empty")
        self.assertTrue(self.queue._subqueues, "Queue started empty")
        self.assertTrue(all(x for x in self.queue._subqueues.values()),
                "Queue started with empty subqueues")

    def test_clear(self):
        """Test `FairQueue.clear`"""
        self.queue.clear()
        self.assertEqual(len(self.queue), 0, "Nonzero length after clear()")
        self.assertFalse([x for x in self.queue],
                         "Content remains in queue after clear()")

    def test_contains(self):
        """Test `FairQueue.__contains__` via ``key in queue``"""
        for key in self.nonexistant_keys:
            self.assertNotIn(key, self.queue,
                "__contains__ should only return values actually in the queue")
        for key in self.queue:
            self.assertIn(key, self.queue,
                "All entries returned by __iter__ should be 'in' the queue")
        for key in self.users:
            self.assertIn(key, self.queue,
                "All entries added to the queue should be 'in' it")

    def test_dump_load_symmetry(self):
        """Test symmetry of `FairQueue.dump` and `FairQueue.load`"""
        dump = self.queue.dump()

        newQueue = self.queue.load(dump)
        self._check_equivalence(newQueue)

        newQueue = self.queue.load(dump, priority_cb=self.queue.priority_cb)
        self.assertIs(self.queue.priority_cb, newQueue.priority_cb)
        self._check_equivalence(newQueue)

        self.assertIsNot(self.queue._buckets, newQueue._buckets,
                "dump() must copy the bucket heap")
        self.assertIsNot(self.queue._subqueues, newQueue._subqueues,
                "dump() must copy the subqueue list")

    def test_delitem(self):
        """Test `FairQueue.__delitem__`"""
        for key in self.nonexistant_keys:
            self.assertRaises(KeyError, self.queue.__delitem__, key)

        for user in self.users:
            self.assertIn(user, self.queue)
            del self.queue[user]
            self._check_invariants()
            self.assertNotIn(user, self.queue,
                    "'del self.queue[user]' must remove 'user' from the queue")

    def test_getitem(self):
        """Test `FairQueue.__getitem__`"""
        # Just to make sure it doesn't behave differently than an empty queue
        for key in self.nonexistant_keys:
            self.assertRaises(KeyError, self.queue.__getitem__, key)

        for user in self.users.values():
            bucket = self.queue[user.bucket_id]
            self.assertEqual(bucket, user.goal)
            self._check_invariants()

            bucket[0], bucket[1] = bucket[1], bucket[0]
            self.assertEqual(bucket, self.queue[user.bucket_id],
                "Mutations to the list returned by __getitem__ must persist.")

            goal_item = bucket[0]
            self.assertEqual(self.queue.pop(user.bucket_id)[1], goal_item,
                "Mutations to lists returned by __getitem__ must affect pop()")

    def test_getitem_safety(self):
        """Test emptying a subqueue using `FairQueue.__getitem__`"""
        # Empty the next subqueue in line
        key = self.queue._buckets[0][1]
        bucket = self.queue[key]
        while bucket:
            bucket.pop()
        self.assertFalse(self.queue[key])

        # Force queue expiry
        next_id = self.queue._buckets[1][1]
        self.assertEqual(self.queue.pop()[0], next_id,
            "Unexpected return from pop() when passing through empty subqueue")

        # Verify the cleanup occurred
        self._check_invariants()

    def test_invalid_pop(self):
        """Test reaction to `FairQueue.pop` on populated queue"""
        for key in self.nonexistant_keys:
            self.assertRaises(KeyError, self.queue.pop, key)

    def test_iter(self):
        """Test queue iteration"""
        #TODO: Once we've got DictMixin, use assertEqual directly on queues.
        self.assertEqual([x for x in self.queue], [x for x in self.users],
                "Queue iteration must return a list of keys (subqueue names)")

        self.queue.push('foo', [1, 2, 3])
        self.queue.push('bar', [1, 2, 3])
        self.assertEqual(list(self.queue), list(self.users) + ['foo', 'bar'],
                "Queue iteration must be in priority order")

    def test_keys(self):
        """Test `FairQueue.keys`"""
        self.assertEqual(self.queue.keys(), [x for x in self.queue],
                "keys() must return the same sequence as iteration")

    def test_len(self):
        """Test `FairQueue.__len__` via ``len(queue)``"""
        total_entries = sum(len(self.queue[x]) for x in self.queue)
        self.assertEqual(len(self.queue), total_entries,
                "Length of the queue must sum the lengths of its subqueues")

    def test_nonzero(self):
        """Test all branches of `FairQueue.__nonzero__`"""
        self.assertTrue(self.queue)

        # Test the hardest-to-reach branch
        for key in self.queue:  # pragma: no branch
            self.queue[key] = []
            break
        self.assertTrue(self.queue)

        for key in self.queue:
            self.queue[key] = []
        self.assertFalse(self.queue)

        self.queue.clear()
        self.assertFalse(self.queue)

    def test_ordering_basic(self):
        """Test ordering behaviour with only non-specific pop() calls"""
        previous = None
        for i in range(0, len(self.queue)):
            key, value = self.queue.pop()
            self.assertNotEqual(key, previous,
                    "At this stage in its development, the queue should never "
                    "allow the same bucket to be the source of two pop() calls"
                    " in a row when all subqueues are of equal length")

    def test_ordering_advanced(self):
        """Test ordering behaviour with subqueue-specific pop() calls"""
        ordered_heap = list(sorted(self.queue))

        for pos in (0, -1, len(ordered_heap) / 2, None, Ellipsis):
            if pos is None:
                key, value = self.queue.pop()
            elif pos is Ellipsis:
                key, value = ('foo', ['bar', 'baz'])
            else:
                key, value = self.queue.pop(ordered_heap[pos])
            self.queue.push(key, value)

            last_user = list(self.queue)[-1]
            self.assertEquals(key, last_user,
                "Users who've just been serviced/added should be at the end of"
                " queue (Last user was %r but expected %r)" % (last_user, key))

    def test_pop(self):
        """Test behaviour of valid `FairQueue.pop` calls without ``key``"""
        while self.queue:
            before = len(self.queue)
            old_hash_record = self.queue._buckets[0]

            key, value = self.queue.pop()

            self.assertNotIn(old_hash_record, self.queue._buckets,
                    "Pop must always update a bucket's hash ordering key")

            self.assertEquals(before - 1, len(self.queue))
            self._check_invariants()
            self.users[key].received(value)

        unsatisfied = [x for x in self.users.values() if not x.is_satisfied()]
        self.assertFalse(unsatisfied,
                'Not all users received their files:\n\t%s' %
                '\n\t'.join('%s: %s, %s' % (x.bucket_id, x.goal, x.done)
                    for x in unsatisfied))

        # Verify deferred subqueue removal
        self._check_invariants()

    def test_pop_with_id(self):
        """Test behaviour of `FairQueue.pop` calls with ``key`` parameter"""
        for key in self.nonexistant_keys:
            self.assertRaises(KeyError, self.queue.pop, key)

        for user in self.users.values():
            while user.bucket_id in self.queue:
                for entry in self.queue._buckets:  # pragma: no branch
                    if entry[1] == user.bucket_id:
                        old_hash_record = entry
                        break

                key, value = self.queue.pop(key=user.bucket_id)

                self.assertEqual(key, user.bucket_id)
                self.assertNotIn(old_hash_record, self.queue._buckets,
                        "Pop must always update a bucket's hash ordering key")

                user.received(value)

            self.assertTrue(user.is_satisfied(),
                "pop(id) failed to retrieve all push(id, ...)'d items")

        # Verify deferred subqueue removal
        self._check_invariants()

    def test_pop_safety(self):
        """Test pop() when heap and subqueues are inconsistent"""

        # Test the hardest-to-reach branch in pop()
        for key in self.queue:  # pragma: no branch
            del self.queue._subqueues[key]
            break
        self.queue.pop()

    def test_setitem(self):
        """Test `FairQueue.__setitem__`"""
        test_key, test_value = 'foo', [1, 2, 3]
        before_value = test_value[:]
        after_value = test_value[1:]

        self.queue['foo'] = test_value
        self.assertEqual(self.queue['foo'], before_value,
                "__setitem__ should insert new subqueues without modification")
        self.assertEqual(self.queue.pop('foo'), ('foo', 1),
                "pop('new_key') must behave as expected after __setitem__")

        self.assertEqual(self.queue['foo'], after_value,
                "pop('new_key') must affect future __getitem__ calls")
        self.assertEqual(self.queue['foo'], test_value,
                "If at all possible, existing references to __setitem__'s "
                "input must remain as mutable references to the subqueue")
