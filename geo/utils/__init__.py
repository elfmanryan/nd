"""
This module provides several helper functions.
"""
import sys
import numpy as np
import xarray as xr
import multiprocessing as mp
from dask import delayed
import datetime
from dateutil.tz import tzutc
from dateutil.parser import parse as parsedate
import itertools

PY2 = sys.version_info < (3, 0)


__all__ = ['str2date',
           'xygrid',
           'dict_product',
           'chunks',
           'array_chunks',
           'block_split',
           'block_merge',
           'xr_split',
           'xr_merge',
           'parallel',
           'select',
           'get_vars_for_dims',
           'expand_variables',
           ]


def str2date(string, fmt=None):
    if fmt is None:
        date_object = parsedate(string)
    else:
        date_object = datetime.datetime.strptime(string, fmt)
    if date_object.tzinfo is None:
        date_object = date_object.replace(tzinfo=tzutc())
    return date_object


def xygrid(ncols, nrows):
    return np.meshgrid(np.arange(nrows), np.arange(ncols), copy=False)


# @profile
# def blockgen(array, bpa):
#     """
#     https://stackoverflow.com/a/16865342
#
#     Creates a generator that yields multidimensional blocks from the given
#     array(_like); bpa is an array_like consisting of the number of blocks
#     per axis (minimum of 1, must be a divisor of the corresponding axis size
#     of array). As the blocks are selected using normal numpy slicing, they
#     will be views rather than copies; this is good for very large
#     multidimensional arrays that are being blocked, and for very large
#     blocks, but it also means that the result must be copied if it is to be
#     modified (unless modifying the original data as well is intended).
#     """
#     bpa = np.asarray(bpa) # in case bpa wasn't already an ndarray
#
#     # parameter checking
#     if array.ndim != bpa.size:
#         # bpa doesn't match array dimensionality
#         raise ValueError("Size of bpa must be equal to the array "
#                          "dimensionality.")
#     if (bpa.dtype != np.int            # bpa must be all integers
#         or (bpa < 1).any()             # all values in bpa must be >= 1
#         or (array.shape % bpa).any()): # % != 0 means not evenly divisible
#         raise ValueError("bpa ({0}) must consist of nonzero positive "
#                          "integers that evenly divide the corresponding "
#                          "array axis size".format(bpa))
#
#     # generate block edge indices
#     rgen = (np.r_[:array.shape[i]+1:array.shape[i]//blk_n]
#             for i, blk_n in enumerate(bpa))
#
#     # build slice sequences for each axis (unfortunately broadcasting
#     # can't be used to make the items easy to operate over
#     c = [[np.s_[i:j] for i, j in zip(r[:-1], r[1:])] for r in rgen]
#
#     # Now to get the blocks; this is slightly less efficient than it could be
#     # because numpy doesn't like jagged arrays and I didn't feel like writing
#     # a ufunc for it.
#     for idxs in np.ndindex(*bpa):
#         blockbounds = tuple(c[j][idxs[j]] for j in range(bpa.size))
#         yield array[blockbounds]


def dict_product(d):
    """Like itertools.product, but works with dictionaries.
    """
    return (dict(zip(d, x))
            for x in itertools.product(*d.values()))


def chunks(l, n):
    """Yield successive n-sized chunks from l.

    https://stackoverflow.com/a/312464

    Parameters
    ----------
    l : iterable
        The list or list-like object to be split into chunks.
    n : int
        The size of the chunks to be generated.

    Yields
    ------
    iterable
        Consecutive slices of l of size n.
    """
    range_fn = range if not PY2 else xrange
    for i in range_fn(0, len(l), n):
        yield l[i:i + n]


def array_chunks(array, n, axis=0, return_indices=False):
    """Chunk an array along the given axis.

    Parameters
    ----------
    array : numpy.array
        The array to be chunked
    n : int
        The chunksize.
    axis : int, optional
        The axis along which to split the array into chunks (default: 0).
    return_indices : bool, optional
        If True, yield the array index that will return chunk rather
        than the chunk itself (default: False).

    Yields
    ------
    iterable
        Consecutive slices of `array` of size `n`.
    """
    if axis >= array.ndim:
        raise ValueError("axis {:d} is out of range for given array."
                         .format(axis))

    arr_len = array.shape[axis]
    range_fn = range if not PY2 else xrange
    for i in range_fn(0, arr_len, n):
        indices = [slice(None), ] * array.ndim
        indices[axis] = slice(i, i+n)
        if return_indices:
            yield indices, array[indices]
        else:
            yield array[indices]


# def blockmerge(array, bpa):
#     """
#     Reassemble a list of arrays as generated by blockgen.
#     """
#     if len(array) != np.prod(bpa):
#         raise ValueError("Length of array must be equal to the product of "
#                          "the shape elements.")
#     # if array.ndim != len(bpa):
#     #     raise ValueError("Size of bpa must be equal to the array "
#     #                      "dimensionality.")
#
#     result = array
#     for i, l in enumerate(bpa[::-1]):
#         result = np.concatenate([_ for _ in chunks(result, l)],
#                                 axis=len(bpa)-i-1)
#         # return np.concatenate([np.concatenate(_, axis=1) for _ in
#         #                        chunks(array, bpa[1])], axis=0)
#     return result


def block_split(array, blocks):
    """Split an ndarray into subarrays according to blocks.

    Parameters
    ----------
    array : numpy.ndarray
        The array to be split.
    blocks : array_like
        The desired number of blocks per axis.

    Returns
    -------
    list
        A list of blocks, in column-major order.

    Examples
    --------
    >>> block_split(np.arange(16).reshape((4,4)))
    [array([[ 0,  1],
            [ 4,  5]]),
     array([[ 2,  3],
            [ 6,  7]]),
     array([[ 8,  9],
            [12, 13]]),
     array([[10, 11],
            [14, 15]])]
    """
    if array.ndim != len(blocks):
        raise ValueError("Length of 'blocks' must be equal to the "
                         "array dimensionality.")

    result = [array]
    for axis, nblocks in enumerate(blocks):
        result = [np.array_split(_, nblocks, axis=axis) for _ in result]
        result = [item for sublist in result for item in sublist]
    return result


def block_merge(array_list, blocks):
    """Reassemble a list of arrays as generated by block_split.

    Parameters
    ----------
    array_list : list of numpy.array
        A list of numpy.array, e.g. as generated by block_split().
    blocks : array_like
        The number of blocks per axis to be merged.

    Returns
    -------
    numpy.array
        A numpy array with dimension len(blocks).
    """
    if len(array_list) != np.prod(blocks):
        raise ValueError("Length of array list must be equal to the "
                         "product of the shape elements.")

    result = array_list
    for i, nblocks in enumerate(blocks[::-1]):
        axis = len(blocks) - i - 1
        result = [np.concatenate(_, axis=axis)
                  for _ in chunks(result, nblocks)]
    return result[0]


def xr_split(ds, dim, chunks, buffer=0):
    """Split an xarray Dataset into chunks.

    Parameters
    ----------
    ds : xarray.Dataset
        The original dataset
    dim : str
        The dimension along which to split.
    chunks : int
        The number of chunks to generate.

    Yields
    ------
    xarray.Dataset
        An individual chunk.
    """
    n = ds.sizes[dim]
    chunksize = int(np.ceil(n / chunks))
    for i in range(chunks):
        low = max(i * chunksize - buffer, 0)
        high = min((i+1) * chunksize + buffer, n)
        idx = slice(low, high)
        chunk = ds.isel(**{dim: idx})
        yield chunk


def xr_merge(ds_list, dim, buffer=0):
    """Reverse split().

    Parameters
    ----------
    ds_list : list of xarray.Dataset
    dim : str
        The dimension along which to concatenate.

    Returns
    -------
    xarray.Dataset
    """
    if buffer > 0:
        idx_first = slice(None, -buffer)
        idx_middle = slice(buffer, -buffer)
        idx_end = slice(buffer, None)
        parts = [ds_list[0].isel(**{dim: idx_first})] + \
                [ds.isel(**{dim: idx_middle}) for ds in ds_list[1:-1]] + \
                [ds_list[-1].isel(**{dim: idx_end})]
    else:
        parts = ds_list
    return xr.concat(parts, dim=dim)


def parallel(fn, dim=None, chunks=None, chunksize=None, merge=True, buffer=0,
             compute=True):
    """
    Parallelize a function that takes an xarray dataset as first argument.

    TODO: make accept numpy arrays as well.

    Parameters
    ----------
    fn : function
        *Must* take an xarray.Dataset as first argument.
    dim : str, optional
        The dimension along which to split the dataset for parallel execution.
        If not passed, try 'lat' as default dimension.
    chunks : int, optional
        The number of chunks to execute in parallel. If not passed, use the
        number of available CPUs.
    chunksize : int, optional
        ... to be implemented
    buffer : int, optional
        (default: 0)
    compute : bool, optional
        If True, return the computed result. Otherwise, return the dask
        computation object (default: True).

    Returns
    -------
    function
        A parallelized function that may be called with exactly the same
        arguments as `fn`.
    """
    if dim is None:
        dim = 'lat'
    if chunks is None:
        chunks = mp.cpu_count()

    def wrapper(ds, *args, **kwargs):
        # if not isinstance(ds, xr.Dataset):
        #     raise ValueError("`parallel` may only be used on functions "
        #                      "accepting an xarray.Dataset as "
        #                      "first argument.")
        if dim not in ds:
            raise ValueError("The dataset has no dimension '{}'."
                             .format(dim))
        #
        # Prechunk the dataset to align memory access with dask
        #
        n = ds.sizes[dim]
        chunksize = int(np.ceil(n / chunks))
        prechunked = ds.chunk({dim: chunksize})

        # Split into parts
        parts = [delayed(fn)(part, *args, **kwargs) for part in
                 xr_split(prechunked, dim=dim, chunks=chunks, buffer=buffer)]
        if merge:
            result = delayed(xr_merge)(parts, dim=dim, buffer=buffer)
        else:
            result = delayed(parts)

        if compute:
            return result.compute()
        else:
            return result

    return wrapper


def select(objects, fn, unlist=True, first=False):
    """Returns a subset of `objects` that matches a range of criteria.

    Parameters
    ----------
    objects : list of obj
        The collection of objects to filter.
    fn : lambda expression
        Filter objects by whether fn(obj) returns True.
    first: bool, optional
        If True, return first entry only (default: False).
    unlist : bool, optional
        If True and the result has length 1 and objects is a list, return the
        object directly, rather than the list (default: True).

    Returns
    -------
    list
        A list of all items in `objects` that match the specified criteria.

    Examples
    --------
    >>> select([{'a': 1, 'b': 2}, {'a': 2, 'b': 2}, {'a': 1, 'b': 1}],
                lambda o: o['a'] == 1)
    [{'a': 1, 'b': 2}, {'a': 1, 'b': 1}]
    """
    filtered = objects
    if type(objects) is list:
        filtered = [obj for obj in filtered if fn(obj)]
    elif type(objects) is dict:
        filtered = {obj_key: obj for obj_key, obj
                    in filtered.items() if fn(obj)}
    if first:
        if len(filtered) == 0:
            return None
        elif type(filtered) is list:
            return filtered[0]
        elif type(filtered) is dict:
            return filtered[list(filtered.keys())[0]]
    elif unlist and len(filtered) == 1 and \
            type(filtered) is list:
        return filtered[0]
    else:
        return filtered


def get_vars_for_dims(ds, dims):
    """
    Return a list of all variables in `ds` which have dimensions `dims`.

    Parameters
    ----------
    ds : xarray.Dataset
    dims : list of str
        The dimensions that each variable must contain

    Returns
    -------
    list of str
        A list of all variable names that have dimensions `dims`.
    """
    return [v for v in ds.data_vars
            if set(ds[v].dims).issuperset(set(dims))]


def expand_variables(da, dim='variable'):
    """
    This is the inverse of xarray.Dataset.to_array().

    Parameters
    ----------
    da : xarray.DataArray
        A DataArray that contains the variable names as dimension.
    dim : str
        The dimension name (default: 'variable').

    Returns
    -------
    xarray.Dataset
        A dataset with the variable dimension in `da` exploded to variables.
    """
    _vars = []
    for v in da[dim]:
        _var = da.sel(**{dim: v})
        _var.name = str(_var[dim].values)
        del _var[dim]
        _vars.append(_var)

    return xr.merge(_vars)
