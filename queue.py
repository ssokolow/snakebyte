#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Queue code for SnakeByte FServe

:attention: Until all listed TODOs are resolved, this API is open to revision.
:todo: Make this and its test suite compatible with Python 3. (This task is
       of a lower priority since, to the best of my knowledge, X-Chat's Python
       harness still uses Python 2.
"""

__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.1"
__license__ = "GNU GPL 3.0 or later"

import heapq, logging, time
log = logging.getLogger(__name__)

class FairQueue(object):
    """A queue that maximizes fairness via the following properties:

     - Users will never be blocked from entering the queue.
     - Users may enqueue as many files as they wish.
     - The number of files one user enqueues will not affect others.
     - Users cannot game the system by adding and removing queue entries.
     - The effect of varying download times on wait times will be minimized.
       **(IN DEVELOPMENT)**

    It accomplishes this through three techniques:
     - The system maintains one queue per user rather than one global queue
     - Whenever a new file is popped from the queue, it comes from the queue
       of the user who has been waiting the longest in wall-clock time.
     - New users are added to the queue as if they have just received a file,
       which ensures that attempts to game the system will either increase
       their wait time or leave it unaffected rather than decreasing it.

    At present, it behaves as a simple round-robin queue based on timestamp
    ordering but, because it uses a heap and can take a callback to calculate
    or recalculate a bucket's priority, changes necessary to implement a
    more advanced form of balancing should be minimal with the existing API
    remaining stable. (With the possible exception of adding a new method
    to force a recalculation of a specific bucket's priority once a download's
    total time to completion has become known.)

    Naturally, it need not only be used for users and lists os files.

    Its API follows that of the ``dict`` built-in wherever possible,
    though minor variations prevent the methods it implements from being
    drop-in compatible the way ``OrderedDict`` is.

    The following API incompatibilities with ``dict`` are known:
        - `__len__` returns the total number of items in all buckets,
          not the number of buckets accessed by `__iter__` and `__getitem__`.
        - `pop`'s behaviour is a cross between ``dict.pop``, ``dict.get``, and
          ``dict.popitem``.

            - ``dict.pop`` may take 1 or 2 arguments, while ``pop`` may take 0
              or 1.
            - ``pop``'s return value is similar to that of ``dict.popitem``
            - After calling ``pop``, the number of keys in the queue may or may
              not have decreased by 1. With ``dict.pop`` it will always
              decrease by 1.

    :todo: Decide on an API for getting the number of buckets more efficiently
           than ``len(list(queue))``.
    :todo: Inherit from ``UserDict.DictMixin`` and unit test what it adds.
    :todo: Once I've got the fserve working, come back and add the support for
           allowing people to receive multiple files in a row to "catch up"
           with those who requested much bigger files.
    """

    def __init__(self, contents=None, priority_cb=None):
        """Initialize the queue, storing any provided initial state
        using a batch-adding algorithm if available.

        :Parameters:
          contents : `dict` or ``iterable of 2-tuples``
            The initial contents for the queue as either a dict or an
            iterable returning ``(bucket, list_of_values)`` pairs.
          priority_cb : ``function(key)``
            A callback which will be used to determine a bucket's new placement
            when updating the queue. Lesser values are considered more urgent.

            ``lambda key: time.time()`` will be used if none is provided.
        """
        self.priority_cb = priority_cb
        if not self.priority_cb:
            self.priority_cb = lambda key: time.time()

        # Initialize the internal data structures
        self.clear()

        if not contents:
            return
        elif hasattr(contents, 'items'):
            contents = contents.items()

        #TODO: Compare performance of alternate algorithms (zip and heapify?)
        for key, values in contents:
            if key in self._subqueues:
                log.warning("Bucket already queued. Merging: %s", key)
            else:
                heapq.heappush(self._buckets, (self.priority_cb(key), key))
            self._subqueues.setdefault(key, []).extend(values)

    def __contains__(self, item):
        """Implements ``key in queue`` as "non-empty bucket exists"."""
        return bool(self._subqueues.get(item))

    def __delitem__(self, key):
        """Remove the specified bucket and all its entries from the queue."""
        if key in self._subqueues:
            # Remove the subqueue
            del self._subqueues[key]

            # ...and find and remove the entry in the heap
            for entry in self._find_key_in_heap(key):
                self._buckets.remove(entry)
            heapq.heapify(self._buckets)
        else:
            raise KeyError(repr(key))

    def __getitem__(self, key):
        """Return a given bucket as a mutable list

        Unlike `pop`, manipulating subqueues this way will not affect which
        bucket will be serviced next.

        :rtype: `list`
        :returns: A mutable list

        :raises KeyError: The requested subqueue does not exist.
        """
        return self._subqueues[key]

    def __iter__(self):
        """Iterate through all non-empty bucket IDs (keys)"""
        for _, key in sorted(self._buckets):
            if self._subqueues.get(key):  # pragma: no branch
                yield key

    def __len__(self):
        """Implements len(queue) as the total number of items in all buckets"""
        return sum(len(x) for x in self._subqueues.values())

    def __nonzero__(self):
        """Maximum-efficiency empty/nonempty test exposed as ``bool()``"""
        for sq in self._subqueues.values():
            if sq:
                return True
        return False

    def __setitem__(self, key, value):
        """Add/replace an entire bucket's subqueue at once"""
        self._add_to_heap(key)
        self._subqueues[key] = value

    def _add_to_heap(self, key):
        """Common code for adding a key to the heap if not already present."""
        if key not in self._subqueues:
            heapq.heappush(self._buckets, (self.priority_cb(key), key))

    def _find_key_in_heap(self, key):
        """Common code for finding a bucket in the heap.

        :rtype: ``tuple``
        :returns: A list of matching entries suitable for ``heap.find()``.

        :note: This is designed on the assumption that `pop` calls without
               a specific bucket key will happen overwhelmingly more often.
        """
        return [x for x in self._buckets if x[1] == key]

    def clear(self):
        """Empty the queue in constant time"""
        self._buckets, self._subqueues = [], {}

    def dump(self):
        """Serialize all state necessary to save the queue to disk using a
        mechanism other than ``pickle``.

        :rtype: `tuple`
        """
        return self._buckets[:], self._subqueues.copy()

    def keys(self):
        """Return a list of all non-empty buckets"""
        return list(self)

    def pop(self, key=None):
        """Remove and return the next item in the queue.

        :Parameters:
         - `key` If provided, bypass automatic bucket selection and retrieve
           the entry from the specified bucket instead.

        :rtype: `tuple`

        :raises IndexError: The queue is empty.
        :raises KeyError: The requested subqueue does not exist.
            (Overrides ``IndexError``)
        """

        heap_id, result = key, None
        while result is None:
            if key is not None and not key in self._subqueues:
                raise KeyError("key not found: %r" % (key,))
            elif not self._buckets:
                raise IndexError("Queue is empty")

            if heap_id is None:
                _, heap_id = heapq.heappop(self._buckets)
            else:
                for entry in self._find_key_in_heap(heap_id):
                    self._buckets.remove(entry)
            heapq.heappush(self._buckets, (self.priority_cb(heap_id), heap_id))

            if heap_id in self._subqueues:
                if self._subqueues[heap_id]:
                    result = heap_id, self._subqueues[heap_id].pop(0)
                if not self._subqueues[heap_id]:
                    del self[heap_id]
                    heap_id = None
            else:
                log.error("Key in heap but not subqueues: %s", heap_id)
                for entry in self._find_key_in_heap(heap_id):
                    self._buckets.remove(entry)
                heap_id = None

        return result

    def push(self, key, value):
        """Add the provided value to the specified bucket in the queue,
        creating the bucket if necessary.

        :Parameters:
         - `key` Any hashable identifier.
         - `value` The value to enqueue. No limitations on type.

        :raises TypeError: The given ``key`` was not hashable
        """
        self._add_to_heap(key)
        self._subqueues.setdefault(key, []).append(value)

    @classmethod
    def load(cls, state, **kwargs):
        """Instantiate a new queue object using state saved by `load`.

        :Parameters:
         - `state` State as saved by `load`.
         - `kwargs` Arguments to be passed to `__init__`.

        :return: A new instance of the class.
        :rtype: `FairQueue`

        :raises TypeError: The given ``state`` was inconsistent with what
            `load` produces.
        """
        if not isinstance(state[0], list):
            raise TypeError("key heap in state must be a list")
        if not isinstance(state[1], dict):
            raise TypeError("subqueues in state must be provided as a dict")

        obj = cls(**kwargs)
        obj._buckets, obj._subqueues = state
        heapq.heapify(obj._buckets)
        return obj
