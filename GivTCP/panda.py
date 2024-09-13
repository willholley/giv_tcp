from GivLUT import GivLUT
from settings import GiV_Settings
import pandas as pd
import numpy as np
logger = GivLUT.logger

def subData(data,item):
    logger.info ("Bad data found in: "+str(item))
    return np.nan

def impute_outliers_IQR(df: np.array, item):
    if GiV_Settings.data_smoother.lower()=="high":
       q1=df.quantile(0.25)
       q3=df.quantile(0.75)
    elif GiV_Settings.data_smoother.lower()=="medium":
       q1=df.quantile(0.15)
       q3=df.quantile(0.85)
    else:
       q1=df.quantile(0.05)
       q3=df.quantile(0.95)
    IQR=q3-q1
    upper = df[~(df>(q3+1.5*IQR))].max()
    lower = df[~(df<(q1-1.5*IQR))].min()
    # replace outliers with NaN then interpolate
    clean = np.where(df > upper,
        subData(df, item),
        np.where(
            df < lower,
            subData(df,item),
            df
            )
        )
    return pd.DataFrame(clean,dtype=float).interpolate(method='linear',limit_direction='both')

def iterate_dict(array):        # Create a publish safe version of the output (convert non string or int datapoints)
    safeoutput = {}
    #dump
    for p_load in array:
        output = array[p_load]
        if isinstance(output, dict):
            temp = iterate_dict(output)
            safeoutput.update(temp)
            #safeoutput[p_load] = output
        else:
            safeoutput[p_load] = output
    return(safeoutput)

def makeFlatStack(CacheStack):
    data=[]
    dp=[]
    for cache in CacheStack:
        data.append(iterate_dict(cache))
    flatstack={}
    for cache in data:
        for item in cache:
            if item in flatstack:
                dp=flatstack[item]
                dp.append(cache[item])
                flatstack[item]=dp
            else:
                flatstack[item]=[cache[item]]
    return flatstack

def outlierRemoval(CacheStack):
    cleanCacheStack={}
    cleanFlatStack={}
    #get all keys in regcachestack
    flatstack=makeFlatStack(CacheStack)

    for item in flatstack:
        test=flatstack[item][0]
        if isinstance(test,(int, float)) and not isinstance(test,bool):
            df = pd.DataFrame(flatstack[item])
            newdf=impute_outliers_IQR(df, item)
            cleanFlatStack[item]=newdf.to_dict(orient='list')[0]
        else:
            cleanFlatStack[item]=flatstack[item]
### NOW put back in the right place...
    for item in cleanFlatStack:
        #find its location in regCache
        newCache=[]
        outp=list(find(item,CacheStack[0]))
        path=outp[0][1:].split('.')
        for i in range (0, len(CacheStack)):
            if len(path)==0:
                CacheStack[i][item]=cleanFlatStack[item]
            elif len(path)==1:
                CacheStack[i][path[0]][item]=cleanFlatStack[item]
            elif len(path)==2:
                CacheStack[i][path[0]][path[1]][item]=cleanFlatStack[item]
            elif len(path)==3:
                CacheStack[i][path[0]][path[1]][path[2]][item]=cleanFlatStack[item]

    return CacheStack

def find(field_name, d, current_path=''):
    if not isinstance(d, dict):
        return

    if field_name in d:
        yield current_path

    for k in d:
        if isinstance(d[k], list):
            index = 0
            for array_element in d[k]:
                for j in find(field_name, array_element, current_path + f'.{k}.[{index}]'):
                    yield j

                index += 1

        elif isinstance(d[k], dict):
            for found in find(field_name, d[k], current_path + f'.{k}'):
                yield found

def updateitem(obj, key, val):
    if key in obj: 
        obj[key]=123
        return obj
    for k, v in obj.items():
        if isinstance(v,dict):
            item = updateitem(v, key,val)
            if item is not None:
                return obj
    return obj