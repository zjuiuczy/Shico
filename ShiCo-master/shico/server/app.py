'''ShiCo server.

Usage:
  app.py  [-f FILES] [-n] [-d] [-p PORT] [-c FUNCTIONNAME] [--use-mmap] [--w2v-format]

  -f FILES         Path to word2vec model files (glob format is supported)
                   [default: word2vecModels/195[0-1]_????.w2v]
  -n,--non-binary  w2v files are NOT binary.
  -d               Run in development mode (debug mode).
  -c FUNCTIONNAME  Name of cleaning function to be applied to output.
                   (example: shico.extras.cleanTermList)
  -p PORT          Port in which ShiCo should run [default: 8000].
  --use-mmap       ??? [default: False]
  --w2v-format     ??? [default: True]
'''
from docopt import docopt
import sys,os,inspect
from flask import Flask, current_app, jsonify,make_response
from flask_cors import CORS
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
pparentdir = os.path.dirname(parentdir)
sys.path.insert(0,pparentdir) 
import sys

import shico 
from shico.vocabularyaggregator import VocabularyAggregator
from shico.vocabularyembedding import doSpaceEmbedding

from shico.format import yearlyNetwork, getRangeMiddle, yearTuplesAsDict
from shico.server.utils import initApp


app = Flask(__name__)
CORS(app)


@app.route('/load-settings')
def appData():
    '''VocabularyMonitor.getAvailableYears service. Takes no parameters.
    Returns JSON structure with years available.'''
    avlYears = app.config['vm'].getAvailableYears()
    yearLabels = {int(getRangeMiddle(y)): y for y in avlYears}
    years = {
        'values': yearLabels,
        'first': min(yearLabels.keys()),
        'last': max(yearLabels.keys())
    }
    canClean = app.config['cleaningFunction'] is not None
    print(app.config['vm'],years,canClean)
    return make_response(jsonify(years=years, cleaning=canClean))


@app.route('/track/<terms>')
def trackWord(terms):
    '''VocabularyMonitor.trackClouds service. Expects a list of terms to be
    sent to the Vocabulary monitor, and returns a JSON representation of the
    response.'''
    params = app.config['trackParser'].parse_args()
    termList = terms.split(',')
    print(termList)
    termList = [term.strip() for term in termList]
    termList = [term.lower() for term in termList]
    print("1")
    results, links = \
        app.config['vm'].trackClouds(termList, maxTerms=params['maxTerms'],
                                     maxRelatedTerms=params['maxRelatedTerms'],
                                     startKey=params['startKey'],
                                     endKey=params['endKey'],
                                     minSim=params['minSim'],
                                     wordBoost=params['wordBoost'],
                                     forwards=params['forwards'],
                                     sumSimilarity=params['boostMethod'],
                                     algorithm=params['algorithm'],
                                     cleaningFunction=app.config['cleaningFunction'] if params[
            'doCleaning'] else None
        )
    print("2",results,app.config['vm'])
    agg = VocabularyAggregator(weighF=params['aggWeighFunction'],
                               wfParam=params['aggWFParam'],
                               yearsInInterval=params['aggYearsInInterval'],
                               nWordsPerYear=params['aggWordsPerYear']
                               )
    print("3")

    aggResults, aggMetadata = agg.aggregate(results)
    print "ResKeys", results.keys()
    print "AggResKeys", aggResults.keys()
    stream = yearTuplesAsDict(aggResults)
    networks = yearlyNetwork(aggMetadata, aggResults, results, links)
    embedded = doSpaceEmbedding(app.config['vm'], results, aggMetadata)
    print(embedded,stream,networks,links)
    return jsonify(stream=stream,
                   networks=networks,
                   embedded=embedded,
                   vocabs=links)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    files = arguments['-f']
    binary = not arguments['--non-binary']
    useMmap = arguments['--use-mmap']
    w2vFormat = arguments['--w2v-format']
    cleaningFunctionStr = arguments['-c']
    port = int(arguments['-p'])

    with app.app_context():
        initApp(current_app, files, binary, useMmap,
                w2vFormat, cleaningFunctionStr)

    # app.debug = arguments['-d']
    app.run(host='0.0.0.0',debug=True)
