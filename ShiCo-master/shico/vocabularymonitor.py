import glob
import os
import six
import threading
from gensim.models import KeyedVectors

from sortedcontainers import SortedDict
from collections import defaultdict, Counter
from functools32 import lru_cache
import math 

class VocabularyMonitor():

    '''Vocabulary Monitor tracks a concept through time. It uses a series of
    gensim Word2Vec models (one for each group of years) to produce a group of
    concept words.

    w2v models are expected to be named after the years which were used in the
    creation of the model (e.g: '1952_1961.w2v'). This is necessary as the
    models names of the models will be used to calculate the chronological
    order and overlap between different models.
    '''

    def __init__(self, globPattern, binary=True, useCache=True, useMmap=True,
                 w2vFormat=True):
        '''Create a Vocabulary monitor using the gensim w2v models located in
        the given glob pattern.

        Arguments:
        globPattern     glob pattern where w2v files can be found
        binary          True if w2v files have been saved as binary
        useCache        ???
        useMmap         ???
        w2vFormat       ???
        '''
        self._models = SortedDict()
        self._loadAllModels(globPattern, binary=True, useCache=useCache,
                            useMmap=useMmap, w2vFormat=w2vFormat)

    def _loadAllModels(self, globPattern, binary, useCache, useMmap, w2vFormat):
        '''Load word2vec models from given globPattern and return a dictionary
        of Word2Vec models.
        '''
        for sModelFile in glob.glob(globPattern):
            # Chop off the path and the extension
            sModelName = os.path.splitext(os.path.basename(sModelFile))[0]

            if w2vFormat:
                assert useMmap == False, 'Mmap cannot be used with w2v format'

                def loader(name): return KeyedVectors.load_word2vec_format(
                    name, binary=binary)
            else:
                mmap = 'r' if useMmap else None

                def loader(name): return KeyedVectors.load(name, mmap=mmap)

            print '[%s]: %s' % (sModelName, sModelFile)
            self._models[sModelName] = loader(sModelFile)
            if useCache:
                print '...caching model ', sModelName
                self._models[sModelName] = CachedW2VModelEvaluator(
                    self._models[sModelName])

    def getAvailableYears(self):
        '''Returns a list of year key's of w2v models currently loaded on this
        vocabularymonitor.'''
        return list(self._models.keys())

    def trackClouds(self, seedTerms, maxTerms=10, maxRelatedTerms=10,
                    startKey=None, endKey=None, minSim=0.0, wordBoost=1.00,
                    forwards=True, sumSimilarity=False, algorithm='adaptive',
                    cleaningFunction=None):
        '''Given a list of seed terms, generate a set of results from the
        word2vec models currently loaded in this vocabularymonitor.

        Keyword arguments:
        seedTerms       -- List of initial seed terms (could be a single
                           string)
        maxTerms        -- Maximum number of terms to be returned from each
                           w2v model.
        maxRelatedTerms -- Maximum number of terms to be returned from each
                           w2v model for each seed term.
        startKey        -- Year key of first w2v model to be used.
        endKey          -- Year key of last w2v model to be used.
        minSim          -- Minimum similarity threshold (in embeded space) for
                           of terms found (terms with similarity smaller than
                           minSim are discarded).
        wordBoost       -- Weight boost automatically given to seed terms.
        forwards        -- Perform search in the forward time direction. Set to
                           False for backward direction.
        sumSimilarity   -- Use the 1-distance as weighting factor. If set to
                           False, weighting is 1 for each occurrence.
        algorithm       -- 'adaptive' or 'non-adaptive' algorithm (adaptive
                           previously known as inlinks). Adaptive algorithm
                           takes results from the current time period and uses
                           them as seeds for the next time period. Non-adaptive
                           algorithm uses the initial seeds for every time
                           period.
        cleaningFunction -- ???

        Returns:
        terms  -- A dictionary with the year key of every model as its keys and
                  lists of (word, weight) tuples as its values.
                  E.g:
                  { '1950_1959': [('w1', 1.0), ('w2', 1.0), ...],
                    '1951_1960': [('w1', 3.0), ('w3', 2.0), ...]
                  }
        links  -- A dictionary with the year key of every model as its keys and
                  dictionaries of term links. Each of these term link
                  dictionaries in turn has seed terms as its keys and lists of
                  (word, distance) tuples as its values.
                  E.g:
                  {'1950_1959': {
                            'w1': [('w2', 0.1), ('w3', 0.6), ... ],
                            }
                   '1951_1960': {
                            'w2': [('w3', 0.2), ('w4', 0.6), ...],
                            'w3': [('w4', 0.2), ('w5', 0.6), ...],
                            }
                  }
        '''
        if isinstance(seedTerms, six.string_types):
            seedTerms = [seedTerms]
        aSeedSet = seedTerms

        # Initialize dicts to be returned
        yTerms = SortedDict()
        yLinks = SortedDict()

        # Keys are already sorted because we use a SortedDict
        sortedKeys = self._models.keys()

        # Select starting key
        if (startKey is not None):
            if startKey not in sortedKeys:
                raise KeyError('Key ' + startKey + ' not a valid model index')
            keyIdx = sortedKeys.index(startKey)
            sortedKeys = sortedKeys[keyIdx:]
        # Select end key
        if (endKey is not None):
            if endKey not in sortedKeys:
                raise KeyError('Key ' + endKey + ' not a valid model index')
            keyIdx = sortedKeys.index(endKey)
            sortedKeys = sortedKeys[:keyIdx]

        # Reverse direction if necessary
        if not forwards:
            sortedKeys = sortedKeys[::-1]

        # Iterate models
        for sKey in sortedKeys:
            if algorithm == 'adaptive':
                terms, links, aSeedSet = \
                    self._trackInlink(self._models[sKey], aSeedSet,
                                      maxTerms=maxTerms,
                                      maxRelatedTerms=maxRelatedTerms,
                                      minSim=minSim,
                                      wordBoost=wordBoost,
                                      sumSimilarity=sumSimilarity,
                                      cleaningFunction=cleaningFunction)
            elif algorithm == 'non-adaptive':
                # Non-adaptive algorithm uses always same set of seeds
                terms, links = \
                    self._trackCore(self._models[sKey], aSeedSet,
                                    maxTerms=maxTerms,
                                    maxRelatedTerms=maxRelatedTerms,
                                    minSim=minSim,
                                    cleaningFunction=cleaningFunction)
            else:
                raise Exception('Algorithm not supported: ' + algorithm)

            # Store results of this time period
            yTerms[sKey] = terms
            yLinks[sKey] = links

        return yTerms, yLinks

    def _trackInlink(self, model, seedTerms, maxTerms=10, maxRelatedTerms=10,
                     minSim=0.0, wordBoost=1.0, sumSimilarity=False,
                     cleaningFunction=None):
        '''Perform in link search'''
        if sumSimilarity:
            terms, links = self._trackCore(
                model, seedTerms, maxTerms=maxTerms,
                maxRelatedTerms=maxRelatedTerms, minSim=minSim,
                wordBoost=wordBoost,  reward=lambda tSim: 1.0 - tSim,
                cleaningFunction=cleaningFunction)
        else:
            terms, links = self._trackCore(
                model, seedTerms, maxTerms=maxTerms,
                maxRelatedTerms=maxRelatedTerms, minSim=minSim,
                cleaningFunction=cleaningFunction)
        # Make a new seed set
        newSeedSet = [word for word, weight in terms]
        return terms, links, newSeedSet

    def _trackCore(self, model, seedTerms, maxTerms=10, maxRelatedTerms=10,
                   minSim=0.0, wordBoost=1.0, reward=lambda x: 1.0,
                   cleaningFunction=None):
        '''Given a list of seed terms, queries the given model to produce a
        list of terms. A dictionary of links is also returned as a dictionary:
        { seed: [(word,weight),...]}'''
        dRelatedTerms = defaultdict(float)
        links = defaultdict(list)

        relatedTermQueries = _getRelatedTerms(
            model, seedTerms, maxRelatedTerms, cleaningFunction)

        # Get the first tier related terms
        for term, newTerms in relatedTermQueries:
            # The terms are always related to themselves
            dRelatedTerms[term] = wordBoost
            links[term].append((term, 0.0))

            for newTerm, tSim in newTerms:
                if tSim < minSim:
                    break
                dRelatedTerms[newTerm] += reward(tSim)
                links[term].append((newTerm, tSim))

        # Select the top N terms with biggest weights (where N=maxTerms)
        topTerms = _getCommonTerms(dRelatedTerms, maxTerms)

        selectedTerms = set(word for word, weight in topTerms)
        links = {seed: _pruned(pairs, selectedTerms)
                 for seed, pairs in links.iteritems()}
        return topTerms, links


def _getRelatedTerms(model, seedTerms, maxRelatedTerms, cleaningFunction):
    queries = []
    threads = []

    for term in seedTerms:
        t = threading.Thread(target=_getRelatedTermsThread,
                             args=(model, term, maxRelatedTerms, queries,
                                   cleaningFunction))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    queries.sort()
    return queries


def _getRelatedTermsThread(model, term, maxRelatedTerms, queries,
                           cleaningFunction):
    try:
        newTerms = model.most_similar(term, topn=maxRelatedTerms)
        modNewTerms = []
        print(newTerms)
        for t,val in newTerms:
            if math.isnan(val):
                # print("NaN")
                modNewTerms.append((t,0.0))
            else:
                modNewTerms.append((t,val))
        newTerms = list(modNewTerms)
        if cleaningFunction is not None:
            newTerms = cleaningFunction(newTerms)

        # list.append is thread safe, so we should be ok
        queries.append((term, newTerms))
    except KeyError:
        queries.append((term, []))
        pass


def _pruned(pairs, words):
    '''Returns a list of (word, weight) tuples which is the same as the given
    list (pairs), except containing only words in the set (words)'''
    return [(word, weight) for word, weight in pairs if word in words]


def _getCommonTerms(terms, N):
    '''Return a the top N terms of the given list. Terms are given as a
    dictionary of { term: weight } and the top terms are the terms with the
    highest weights.'''
    termCounter = Counter(terms)
    topTerms = termCounter.most_common(N)
    return topTerms


class CachedW2VModelEvaluator():

    '''Wrapper class for applying lru_cache. This will keep maxsize=1000
    results from each model cached, making querying much faster.'''

    def __init__(self, model):
        self._model = model
        self.vocab = model.vocab

    @lru_cache(maxsize=1000)
    def most_similar(self, term, topn):
        return self._model.most_similar(term, topn=topn)

    def n_similarity(self, term1, term2):
        try:
            return self._model.n_similarity(term1, term2)
        except KeyError:
            return 0
