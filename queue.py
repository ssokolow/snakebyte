#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Queue code for SnakeByte FServe"""

__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.1"
__license__ = "GNU GPL 3.0 or later"

import heapq, logging, time
log = logging.getLogger(__name__)

#TODO: Decide how to allow querying of whether anything is waiting in the queue
class FairQueue(object):
    """A queue that maximizes fairness via the following properties:

     - Users will never be blocked from entering the queue.
     - Users may enqueue as many files as they wish.
     - The number of files one user enqueues will not affect others.
     - The effect of varying download times on wait times will be minimized.
     - Users cannot game the system by adding and removing queue entries.

    It accomplishes this through three techniques:
     - The system maintains one queue per user rather than one global queue
     - Whenever a new file is popped from the queue, it comes from the queue
       of the user who has been waiting the longest in wall-clock time.
     - New users are added to the queue as if they have just received a file,
       which ensures that attempts to game the system will either increase
       their wait time or leave it unaffected rather than decreasing it.

    Furthermore, as indicated by the API, this queue is of general utility.
    A user is simply an example of a bucket identifier and values need not be
    paths to files. Also, nothing inherently ties this API to use for downloads.
    """
    def __init__(self, contents=None, priority_cb=None):
        """Initialize the queue, storing any provided initial state
        using a batch-adding algorithm if available.

        :Parameters:
          contents : `dict` or ``iterable of 2-tuples``
            The initial contents for the queue as either a dict or an
            iterable returning ``(bucket, list_of_values)`` pairs.
          priority_cb : ``function(bucket_id)``
            A callback which will be used to determine a bucket's new placement
            when reordering the queue. Lesser values are treated as more urgent.

            ``lambda bucket_id: time.time()`` will be used if none is provided.
        """
        self._buckets, self._subqueues = [], {}

        self.priority_cb = priority_cb
        if not self.priority_cb:
            self.priority_cb = lambda bucket_id: time.time()

        if not contents:
            return
        elif isinstance(contents, dict):
            contents = contents.items()

        for pos, (bucket_id, values) in enumerate(contents):
            if bucket_id in self._subqueues:
                log.warning("Bucket already queued. Merging: %s", bucket_id)
            else:
                heapq.heappush(self._buckets, (pos, bucket_id))
            self._subqueues.setdefault(bucket_id, []).extend(values)

    def dump(self):
        """Serialize all state necessary to save the queue to disk using a
        mechanism other than ``pickle``.

        :rtype: `tuple`
        """
        return self._buckets, self._subqueues

    def get(self, bucket_id=None):
        """Remove and return the next item in the queue.

        :Parameters:
         - `bucket_id` If provided, bypass automatic bucket selection and
           retrieve the entry from the specified bucket instead.

        :rtype: `tuple`

        :raises IndexError: The queue is empty.
        :raises KeyError: The requested subqueue does not exist.
            (Overrides ``IndexError``)
        """

        target_id, result = bucket_id, None
        while not result:
            if bucket_id and not bucket_id in self._subqueues:
                raise KeyError("bucket_id not found: %r" % (bucket_id,))
            elif not self._buckets:
                raise IndexError("Queue is empty")

            if not target_id:
                _, target_id = heapq.heappop(self._buckets)
                heapq.heappush(self._buckets, (self.priority_cb(target_id), target_id))

            if target_id in self._subqueues:
                #TODO: Unit test for when list returned by get_bucket() is emptied.
                if self._subqueues[target_id]:
                    result = target_id, self._subqueues[target_id].pop(0)

                #TODO: Maybe empty subqueues should stick around until the next
                #      get() on them so people have a grace period to queue more
                #      without losing their place.
                #TODO: Move this into a drop_bucket method and unit test it.
                if not self._subqueues[target_id]:
                    # Remove the subqueue
                    del self._subqueues[target_id]

                    # ...and find and remove the entry in the heap
                    dead_buckets = [x for x in self._buckets if x[1] == target_id]
                    for entry in dead_buckets:
                        self._buckets.remove(entry)
                    heapq.heapify(self._buckets)

                    #target_id = bucket_id
                    target_id = None

        return result

    def get_bucket(self, bucket_id):
        """Return a given bucket as a mutable list

        Unlike `get`, manipulating subqueues this way will not affect which
        bucket will be serviced next.

        :rtype: `list`
        :returns: A mutable list

        :raises KeyError: The requested subqueue does not exist.
        """
        return self._subqueues[bucket_id]

    def put(self, bucket_id, value):
        """Add the provided value to the specified bucket in the queue,
        creating the bucket if necessary.

        :Parameters:
         - `bucket_id` Any hashable identifier.
         - `value` The value to enqueue. No limitations on type.

        :raises TypeError: The given ``bucket_id`` was not hashable
        """
        if bucket_id not in self._subqueues:
            heapq.heappush(self._buckets, (self.priority_cb(bucket_id), bucket_id))
        self._subqueues.setdefault(bucket_id, []).append(value)

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
            raise TypeError("bucket_id heap in saved state must be a list")
        if not isinstance(state[1], dict):
            raise TypeError("subqueues in saved state must be provided as a dict")

        obj = cls(**kwargs)
        obj._buckets, obj._subqueues = state
        heapq.heapify(obj._buckets)
        return obj
