#import matplotlib # Its not that this file is responsible for doing plotting, but it calls many modules that are, such that it needs to pre-empt
# setting of an appropriate backend.
#matplotlib.use('agg')

import numpy as np
import dask.bag as db
import pandas as pd
# Import get_neab has to happen exactly here. It has to be called only on
from neuronunit import tests
from neuronunit.optimization import get_neab
from neuronunit.models.reduced import ReducedModel
from neuronunit.optimization.model_parameters import model_params, path_params
import numpy
import dask.bag as db
from neuronunit.optimization import model_parameters as modelp
from itertools import repeat
import copy
from neuronunit.optimization import get_neab
from pyneuroml import pynml
from dask.distributed import Client
import dask.bag as db
def write_opt_to_nml(path,param_dict):
    '''
    Write optimimal simulation parameters back to NeuroML.
    '''
    orig_lems_file_path = path_params['model_path']
    more_attributes = pynml.read_lems_file(orig_lems_file_path,
                                           include_includes=True,
                                           debug=False)
    for i in more_attributes.components:
        new = {}
        if str('izhikevich2007Cell') in i.type:
            for k,v in i.parameters.items():
                units = v.split()
                if len(units) == 2:
                    units = units[1]
                else:
                    units = 'mV'
                new[k] = str(param_dict[k]) + str(' ') + str(units)
            i.parameters = new
    more_attributes.export_to_file(path+'.nml')
    return

def map_wrapper(function_item,list_items,other_args=None):
    from dask import distributed
    c = distributed.Client()
    NCORES = len(C.ncores().values())-2
    b0 = db.from_sequence(list_items, npartitions = NCORES)
    init = len(list_items)
    if other_args is not None:
        processed_list = list(db.map(function_item,b0,other_args).compute())
    else:
        processed_list = db.map(function_item,b0)
        processed_list = list(processed_list.compute())

    assert len(processed_list) == init
    # https://distributed.readthedocs.io/en/latest/memory.html
    return processed_list

def dtc_to_rheo(xargs):
    dtc,rtest,backend = xargs
    dtc.model_path = path_params['model_path']
    LEMS_MODEL_PATH = path_params['model_path']
    if backend != 'glif':
        model = ReducedModel(LEMS_MODEL_PATH,name=str('vanilla'),backend='NEURON')
        model.set_attrs(dtc.attrs)
        dtc.scores = {}
        dtc.score = {}
    else:
        from neuronunit.models.interfaces import glif
        model = glif.GC()

    score = rtest.judge(model,stop_on_error = False, deep_error = True)
    if score.sort_key is not None:
        if hasattr(dtc,'scores'):
            dtc.scores[str(rtest)] = 1 - score.sort_key
        else:
            dtc.scores = {}
            dtc.scores[str(rtest)] = 1 - score.sort_key
    dtc.rheobase = score.prediction

    return dtc

def nunit_evaluation(dtc,tests,backend=None):
    # Inputs single data transport container modules, and neuroelectro observations that
    # inform test error error_criterion
    # Outputs Neuron Unit evaluation scores over error criterion
    assert (len(tests) == 7 or len(tests) == 8)

    dtc.model_path = path_params['model_path']
    LEMS_MODEL_PATH = path_params['model_path']
    assert dtc.rheobase is not None
    if backend == None:
        from neuronunit.models.reduced import ReducedModel
        model = ReducedModel(LEMS_MODEL_PATH,name=str('vanilla'),backend=('NEURON',{'DTC':dtc}))
        model.set_attrs(dtc.attrs)
        tests[0].prediction = dtc.rheobase
        model.rheobase = dtc.rheobase['value']
    else:
        from neuronunit.models.interfaces import glif
        model = glif.GC()#ReducedModel(LEMS_MODEL_PATH,name=str('vanilla'),backend=('NEURON',{'DTC':dtc}))
        tests[0].prediction = dtc.rheobase
        model.rheobase = dtc.rheobase['value']
    #from dask import dataframe as dd
    if dtc.score is None:
        dtc.score = {}

    for k,t in enumerate(tests[1:-1]):
        t.params = dtc.vtest[k]
        print(t.params)
        score = None
        score = t.judge(model,stop_on_error = False, deep_error = False)
        if score.sort_key is not None:
            # dtc.scores.get(str(t), score.sort_key)
            # dtc.score.get(str(t), score.sort_key-1)
            dtc.scores[str(t)] = 1.0 - score.sort_key
            print(str(t),score.sort_key)
            if not hasattr(dtc,'score'):
                dtc.score = {}
            dtc.score[str(t)] = score.sort_key
        else:
            pass
    return dtc


def evaluate(dtc):
    fitness = [ 1.0 for i in range(0,len(dtc.scores.keys())) ]
    for k,t in enumerate(dtc.scores.keys()):
        fitness[k] = dtc.scores[str(t)]#.sort_key
    import pdb; pdb.set_trace()    
    return fitness[0],fitness[1],\
           fitness[2],fitness[3],\
           fitness[4],fitness[5],\
           fitness[6],#fitness[7],

def get_trans_list(param_dict):
    trans_list = []
    for i,k in enumerate(list(param_dict.keys())):
        trans_list.append(k)
    return trans_list

def format_test(xargs):
    '''
    pre format the current injection dictionary based on pre computed
    rheobase values of current injection.
    This is much like the hooked method from the old get neab file.
    '''
    dtc,tests = xargs
    #import copy
    import quantities as pq
    #import copy
    dtc.vtest = None
    dtc.vtest = {}
    #from neuronunit.optimization import get_neab
    #tests = get_neab.tests
    for k,v in enumerate(tests):
        dtc.vtest[k] = {}
        #dtc.vtest.get(k,{})
        dtc.vtest[k]['injected_square_current'] = {}
    for k,v in enumerate(tests):
        if k == 1 or k == 2 or k == 3:
            # Negative square pulse current.
            dtc.vtest[k]['injected_square_current']['duration'] = 100 * pq.ms
            dtc.vtest[k]['injected_square_current']['amplitude'] = -10 *pq.pA
            dtc.vtest[k]['injected_square_current']['delay'] = 30 * pq.ms

        if k == 0 or k == 4 or k == 5 or k == 6 or k == 7:
            # Threshold current.
            dtc.vtest[k]['injected_square_current']['duration'] = 1000 * pq.ms
            dtc.vtest[k]['injected_square_current']['amplitude'] = dtc.rheobase['value']
            dtc.vtest[k]['injected_square_current']['delay'] = 250 * pq.ms # + 150
    return dtc



def update_dtc_pop(pop, td = None, backend = None):

    '''
    inputs a population of genes/alleles, the population size MU, and an optional argument of a rheobase value guess
    outputs a population of genes/alleles, a population of individual object shells, ie a pickleable container for gene attributes.
    Rationale, not every gene value will result in a model for which rheobase is found, in which case that gene is discarded, however to
    compensate for losses in gene population size, more gene samples must be tested for a successful return from a rheobase search.
    If the tests return are successful these new sampled individuals are appended to the population, and then their attributes are mapped onto
    corresponding virtual model objects.
    '''

    import copy
    import numpy as np
    from deap import base
    toolbox = base.Toolbox()
    pop = [toolbox.clone(i) for i in pop ]
    def transform(ind):
        import dask.bag as db
        from neuronunit.optimization.data_transport_container import DataTC
        dtc = DataTC()
        import neuronunit
        LEMS_MODEL_PATH = str(neuronunit.__path__[0])+str('/models/NeuroML2/LEMS_2007One.xml')
        if backend is not None:
            dtc.backend = backend
        else:
            dtc.backend = 'NEURON'

        dtc.attrs = {}
        for i,j in enumerate(ind):
            dtc.attrs[str(td[i])] = j
        dtc.evaluated = False
        return dtc
    if len(pop) > 1:
        b = db.from_sequence(pop, npartitions=8)
        dtcpop = list(db.map(transform,b).compute())

    else:
        # In this case pop is not really a population but an individual
        # but parsimony of naming variables
        # suggests not to change the variable name to reflect this.
        dtcpop = list(transform(pop))
    return dtcpop


def update_deap_pop(pop, tests, td, backend = None):
    '''
    Inputs a population of genes (pop).
    Returned neuronunit scored DTCs (dtcpop).
    This method converts a population of genes to a population of Data Transport Containers,
    Which act as communicatable data types for storing model attributes.
    Rheobase values are found on the DTCs
    DTCs for which a rheobase value of x (pA)<=0 are filtered out
    DTCs are then scored by neuronunit, using neuronunit models that act in place.
    '''
    orig_MU = len(pop)
    dtcpop = list(update_dtc_pop(pop, td))
    rheobase_test = tests[0]
    xargs = zip(dtcpop,repeat(rheobase_test),repeat('glif'))
    dtcpop = list(map(dtc_to_rheo,xargs))

    dtcpop = list(filter(lambda dtc: dtc.rheobase['value'] > 0.0 , dtcpop))
    xargs = zip(dtcpop,repeat(tests))
    dtcpop = list(map(format_test,xargs))
    # https://distributed.readthedocs.io/en/latest/memory.html
    #dtcpop = map_wrapper(nunit_evaluation,dtcpop,other_args=tests)
    for d in dtcpop:
        d = nunit_evaluation(d,tests,backend='glif')
    import copy
    dtcpop_ = copy.copy(dtcpop)
    #dtcpop_ = map_wrapper(nunit_evaluation,dtcpop,other_args=tests)
    del dtcpop
    #del dtcpop
    #dtcpop = list(filter(lambda dtc: not isinstance(dtc.scores['RheobaseTestP'],type(None)),dtcpop_))
    dtcpop = list(filter(lambda dtc: not type(None) in (list(dtc.scores.values())), dtcpop_))
    # This call deletes everything
    #dtcpop = list(filter(lambda dtc: not (numpy.isinf(x) for x in list(dtc.scores.values())), dtcpop))
    for i,d in enumerate(dtcpop):
        pop[i].rheobase = d.rheobase
    return zip(dtcpop, pop)


def create_subset(nparams=10, provided_keys=None):
    from neuronunit.optimization import model_parameters as modelp
    import numpy as np
    mp = modelp.model_params
    key_list = list(mp.keys())
    if type(provided_keys) is type(None):
        key_list = list(mp.keys())
        reduced_key_list = key_list[0:nparams]
    else:
        reduced_key_list = provided_keys
    subset = { k:mp[k] for k in reduced_key_list }
    return subset
