#!/usr/bin/env python
"""

General-purpose tools to semantically tabulate, diff and superset Fortran namelist files.
Also includes a command-line interface.

Latest version: https://github.com/aekiss/nmltab
Author: Andrew Kiss https://github.com/aekiss
Apache 2.0 License http://www.apache.org/licenses/LICENSE-2.0.txt
"""


# TODO: handle multiple groups with the same name. tidy should consolidate names, with definitions in later groups taking priority if the same name is defined in two groups of the same name. What happens if a name is repeated in one group? Ask Marshall.

from __future__ import print_function

# for testing my modified f90nml
# import sys
# sys.path.insert(0, '/Users/andy/Documents/COSIMA/github/aekiss/f90nml') # BUG: doesn't work with /Users/andy/anaconda/bin/python3 /Users/andy/bin/nmltab.py --format latex    new/control/025deg_jra55_ryf/ice/input_ice_gfdl.nml

import f90nml  # from http://f90nml.readthedocs.io
import filecmp
import textwrap
import copy
import warnings
import collections
import os
import itertools

# from IPython.display import display, Markdown


def nmldict(nmlfnames):
    """
    Return OrderedDict of the groups and variables in Fortran namelist files.

    Parameters
    ----------
    nmlfnames : str, tuple or list
        string, or tuple or list of any number of namelist file path strings.
        Repeated files are silently ignored.

    Returns
    -------
    OrderedDict
        OrderedDict with `key`:`value` pairs where
        `key` is filename path string (in supplied order)
        `value` is complete Namelist from filename as returned by f90nml.read

    """
    if isinstance(nmlfnames, str):
        nmlfnames = [nmlfnames]

    nmlall = collections.OrderedDict()  # dict keys are nml paths, values are Namelist dicts
    for nml in nmlfnames:
        nmlall[nml] = f90nml.read(nml)
        if len(nmlall[nml]) == 0:
            warnings.warn('{} does not contain any namelist data'.format(nml))
    return nmlall


def superset(nmlall):
    """
    Return dict of groups and variables present in any of the input Namelists.

    Parameters
    ----------
    nmlall : dict or OrderedDict
        dict (e.g. returned by nmldict) with `key`:`value` pairs where
        `key` is arbitrary (typically a filename string)
        `value` is Namelist (typically from filename via f90nml.read)

    Returns
    -------
    dict
        dict with `key`:`value` pairs where
        `key` is group name (including all groups present in any input Namelist)
        `value` is Namelist for group (including every variable present in this
            group in any input Namelist)

    """
    # if len(nmlall) == 1:  # just do a deep copy of the only value
    #     nmlsuperset = copy.deepcopy(nmlall[list(nmlall.keys())[0]])
    # else:
    nmlsuperset = {}
    for nml in nmlall:
        nmlsuperset.update(nmlall[nml])
    # nmlsuperset now contains all groups that were in any nml
    for group in nmlsuperset:
        # to avoid the next bit changing the original groups
        nmlsuperset[group] = nmlsuperset[group].copy()
        # if isinstance(nmlallsuperset[group], list):
        #     for gr in nmlall[nml][group]:
        #         nmlsuperset[group].update(gr)
        for nml in nmlall:
            if group in nmlall[nml]:
                # print("nml={}, group={}".format(nml, group))
                # if isinstance(nmlall[nml][group], list):
                #     for gr in nmlall[nml][group]:
                #         nmlsuperset[group].update(gr)
                # else:
                nmlsuperset[group].update(nmlall[nml][group])
    # nmlsuperset groups now contain all keys that were in any nml
    return nmlsuperset


def nmldiff(nmlall):
    """
    In-place remove every group/variable that's the same in all file Namelists.

    Parameters
    ----------
    nmlall : dict or OrderedDict
        dict (e.g. returned by nmldict) with `key`:`value` pairs where
        `key` is arbitrary (typically a filename path string)
        `value` is Namelist (typically from filename via f90nml.read)

    Returns
    -------
    dict or OrderedDict
        In-place modified input dict with `key`:`value` pairs where
        `key` is arbitrary (typically a filename path string)
        `value` is Namelist from nmlall, with any variable
                common to all other keys (i.e. files) in input removed.
                Groups whose contents are identical are also removed.

    """
# Create diff by removing common groups/variables from nmlall.
# This is complicated by the fact group names / variable names may differ
# or be absent across different nml files.
#
# First make a superset that has all group names and variables that
# appear in any nml file
    nmlsuperset = superset(nmlall)

    # now go through nmlall and remove any groups / variables from nmlall that
    #   are identical to superset in all nmls
    # first delete any variables that are common to all nmls, then delete
    #   any empty groups common to all nmls
    for group in nmlsuperset:
        # init: whether group is present and identical in all namelist files
        deletegroup = True
        for nml in nmlall:
            deletegroup = deletegroup and (group in nmlall[nml])
        if deletegroup:  # group present in all namelist files
            for var in nmlsuperset[group]:
                # init: whether variable is present and identical
                #   in all namelist files
                deletevar = True
                for nml in nmlall:
                    deletevar = deletevar and (var in nmlall[nml][group])
                if deletevar:  # variable is present in all namelist files
                    for nml in nmlall:
                        # ... now check if values match in all namelist files
                        # print("nml={}, group={}, var={}".format(nml, group, var))
                        deletevar = deletevar and \
                            (nmlall[nml][group][var] ==
                             nmlsuperset[group][var])
                    if deletevar:
                        for nml in nmlall:
                            # delete var from this group in all nmls
                            del nmlall[nml][group][var]
            for nml in nmlall:
                deletegroup = deletegroup and (len(nmlall[nml][group]) == 0)
            if deletegroup:
                # group is common to all nmls and now empty so delete
                for nml in nmlall:
                    del nmlall[nml][group]
    return nmlall


def prunefilelist(fnames):
    """
    Remove names of files with identical content to the previous file in list.

    Parameters
    ----------
    fnames : List
        List of any number of file path strings.

    Returns
    -------
    List
        New list in same order as fnames but including only names of files with
        content that is not identical to that of the previous file in the list.
        Non-existent files are ignored and not included in output list.

    Examples
    --------
        >>> nmlprune(nmldict(prunefilelist(glob.glob(*.nml))))

    """
    fntmp = [fn for fn in fnames if os.path.isfile(fn)]
    if len(fntmp) <= 1:
        outfnames = fntmp
    else:
        outfnames = []
        outfnames.append(fntmp[0])
        for fn in fntmp[1:]:
            if not(filecmp.cmp(outfnames[-1], fn, shallow=False)):
                outfnames.append(fn)
    return outfnames


def nmlprune(nmlall, ignore={}):
    """
    In-place remove all Namelists that are the same as the previous one in nmlall.

    Does nothing if nml is not an OrderedDict.

    Parameters
    ----------
    nmlall : OrderedDict
        OrderedDict (e.g. returned by nmldict) with `key`:`value` pairs where
        `key` is arbitrary (typically a filename path string)
        `value` is Namelist (typically from filename via f90nml.read)
        For efficiency use prunefilelist on file list before passing to nmldict.

    ignore : dict, optional
        dict specifying namelist variables whose differences should be ignored.
        key is namelist group
        value is a list of variable names within that group

    Returns
    -------
    OrderedDict
        In-place modified input OrderedDict with `key`:`value` pairs where
        `key` is arbitrary (typically a filename path string)
        `value` is Namelist from nmlall, with any variable
                common to all other keys (i.e. files) in input removed.
                Groups whose contents are identical are also removed.

    Examples
    --------
        >>> nmlprune(nmldict(prunefilelist(glob.glob(*.nml))))
    """
    if len(nmlall) > 1:
        idx = 0
        while True:
            # need deepcopy to avoid in-place modification by nmldiff
            pair = copy.deepcopy(collections.OrderedDict(
                        itertools.islice(nmlall.items(), idx, idx+2)))
            for group in ignore:
                for var in ignore[group]:
                    for fn in pair:
                        if group in pair[fn]:
                            if var in pair[fn][group]:
                                del pair[fn][group][var]
            nmldiff(pair)
            if max([len(x) for x in pair.values()]) == 0:
                del nmlall[list(pair.keys())[1]]  # remove 2nd of pair
            else:
                idx += 1  # 2nd of pair is different from first, so retain it
            if idx > len(nmlall)-2:
                break
    return nmlall


def tidy_overwrite(nmlall):
    """
    Overwrite namelist files with parsed namelist data from those files,
    sorted alphabetically by group then variable name.
    (Sorting requires https://github.com/marshallward/f90nml/pull/50).
    Files with no namelist data are left untouched.

    Parameters
    ----------
    nmlall : dict or OrderedDict
        dict (e.g. returned by nmldict) with `key`:`value` pairs where
        `key` is filename path string to be overwritten
        `value` is Namelist (typically from filename via f90nml.read)

    Returns
    -------
    None

    """
    for nml in nmlall:
        if len(nmlall[nml]) > 0:
            nmlall[nml].sort = True  # requires https://github.com/marshallward/f90nml/pull/50
            nmlout = nml + '-tmp'
            try:
                f90nml.write(nmlall[nml], nmlout)
                os.replace(nmlout, nml)
            except:  # TODO: don't use bare except
                warnings.warn("Error {} tidying '{}'; file left untouched. \
Delete part-converted file '{}' before trying again."
                              .format(sys.exc_info()[0], nml, nmlout))
    return None


def strnmldict(nmlall, format='', masterswitch=''):
    """
    Return string representation of dict of Namelists.

    Parameters
    ----------
    nmlall : dict or OrderedDict
        dict (e.g. returned by nmldict) with `key`:`value` pairs where
        `key` is arbitrary (typically a filename path string)
        `value` is Namelist (typically from filename via f90nml.read)

    format : str, optional, case insensitive
        'md' or 'markdown': markdown string output
        'latex': latex string output
        anything else: standard string output

    masterswitch : str, optional, case insensitive
        key with boolean value that disables other variables in group
        if present and false, e.g. 'use_this_module' in MOM.
        NB: this key might be absent in namelist differences.
        Only used for format='latex'.

    Returns
    -------
    string
        String representaion of nmlall.
        Default lists alphabetically by group, variable, then dict key,
        with undefined namelist variables shown as blank.

    """
    def latexstr(item):
        return item.replace('_', '\\_').replace('/', '\\slash ').replace('%', '\%')

    def latexrepr(item):
        if isinstance(item, str):
            return "'" + latexstr(item) + "'"
        elif isinstance(item, float):
            return '\\num*{' + repr(item).replace('e+0', 'e+').replace('e-0', 'e-') + '}{}'
        elif isinstance(item, list):
            s = ''
            for i in item:
                s += latexrepr(i) + ', '
            return s[:-2]
        else:
            return repr(item)

    # TODO: fail on unknown format
    # TODO: put data format in Fortran syntax eg for booleans and arrays - does nf90nml do this?
    #    - see f90repr in namelist.py: https://github.com/marshallward/f90nml/blob/master/f90nml/namelist.py#L405
    nmlss = superset(nmlall)
    nmldss = superset(nmldiff(copy.deepcopy(nmlall)))  # avoid in-place modification
    fnames = list(nmlall.keys())
    colwidth = max((len(f) for f in fnames), default=0)
    # TODO: would be faster & more efficient to .append a list of strings
    # and then join them:
    # http://docs.python-guide.org/en/latest/writing/structure/#mutable-and-immutable-types
    st = ''
    if format.lower() in ('md', 'markdown'):
        if len(nmlss) > 0:
            st += '| ' + 'File'.ljust(colwidth) + ' | '
            nvar = 0
            for group in sorted(nmlss):
                for var in sorted(nmlss[group]):
                    st += '&' + group + '<br>' + var + ' | '
                    nvar += 1
            st += '\n|-' + '-' * colwidth + ':|' + '--:|' * nvar
            for fn in fnames:
                st += '\n| ' + fn + ' | '
                for group in sorted(nmlss):
                    for var in sorted(nmlss[group]):
                        if group in nmlall[fn]:
                            if var in nmlall[fn][group]:
                                st += repr(nmlall[fn][group][var])  # TODO: use f90repr
                        st += ' | '
            st += '\n'
    elif format.lower() == 'latex':
        if len(nmlss) > 0:
            st += textwrap.dedent("""
            % Latex tabulation of Fortran namelist, auto-generated by nmltab.py <https://github.com/aekiss/nmltab>
            %
            % Include this file in a latex document using \\import{path/to/this/file}.
            % The importing document requires
            % \\usepackage{ltablex, array, sistyle}
            % and possibly (depending on definitions below)
            % \\usepackage{hyperref, color}
            % and also needs to define 'nmldiffer', 'nmllink' and 'ignored' commands, e.g.
            % \\newcommand{\\nmldiffer}[1]{#1} % no special display of differing variables
            % \\newcommand{\\nmldiffer}[1]{\\textbf{#1}} % bold display of differing variables
            % \\definecolor{hilite}{cmyk}{0, 0, 0.9, 0}\\newcommand{\\nmldiffer}[1]{\\colorbox{hilite}{#1}}\\setlength{\\fboxsep}{0pt} % colour highlight of differing variables (requires color package)
            % \\newcommand{\\nmllink}[2]{#1} % don't link variables
            % \\newcommand{\\nmllink}[2]{\href{https://github.com/mom-ocean/MOM5/search?q=#2}{#1}} % link variables to documentation (requires hyperref package)
            % \\newcommand{\\ignored}[1]{#1} % no special display of ignored variables
            % \\definecolor{ignore}{gray}{0.7}\\newcommand{\\ignored}[1]{\\textcolor{ignore}{#1}} % gray display of ignored variables (but only in groups where masterswitch key is present and false, so may not work well for differences; requires color package)
            % and also define the length 'nmllen' that sets the column width, e.g.
            % \\newlength{\\nmllen}\\setlength{\\nmllen}{12ex}

            """)
            st += '\\newcolumntype{R}{>{\\raggedleft\\arraybackslash}p{\\nmllen}}\n'
            st += '\\begin{tabularx}{\\linewidth}{X' + 'R' * len(fnames) + '}\n'
            st += '\\hline\n'
            st += '\\textbf{Group\\quad\\hfill Variable}'
            # for fn in rmcommonprefix(rmcommonsuffix(fnames)):
            for fn in fnames:
                st += '\t & \t\\textbf{' + latexstr(fn) + '}'
            st += ' \\\\\n\\hline\\endfirsthead\n'
            st += '\\hline\n'
            st += '\\textbf{Group (continued)\\quad\\hfill Variable}'
            # for fn in rmcommonprefix(rmcommonsuffix(fnames)):
            for fn in fnames:
                st += '\t & \t\\textbf{' + latexstr(fn) + '}'
            st += ' \\\\\n\\hline\\endhead\n'
            for group in sorted(nmlss):
                for i, var in enumerate(sorted(nmlss[group])):
                    if i == 0:  # only show group once
                        gr = '\\&\\nmllink{{{}}}{{{}}}'.format(
                            latexstr(group), group)
                    else:
                        gr = ''
                    st1 = '{} \\hfill \\nmllink{{{}}}{{{}}}'.format(
                        gr, latexstr(var), var)  # replaced below if differences
                    if group in nmldss:
                        if var in nmldss[group]:  # new st1 if differences
                            st1 = '{} \\hfill \\nmllink{{\\nmldiffer{{{}}}}}{{{}}}'.format(
                                gr, latexstr(var), var)
                    st += st1
                    for fn in fnames:
                        st += '\t & \t'
                        if group in nmlall[fn]:
                            if var in nmlall[fn][group]:
                                st1 = latexrepr(nmlall[fn][group][var])  # TODO: use f90repr
                                if masterswitch in nmlall[fn][group]:
                                    if not nmlall[fn][group][masterswitch] \
                                            and var != masterswitch:
                                        st1 = '\\ignored{' + st1 + '}'
                                st += st1
                    st += ' \\\\\n'
                if len(nmlss[group]) > 0:
                    st += '\\hline\n'
            st += '\\end{tabularx}\n'
    else:
        for group in sorted(nmlss):
            for var in sorted(nmlss[group]):
                st += ' ' * (colwidth + 2) + '&{}\n'.format(group)
                st += ' ' * (colwidth + 2) + ' {}\n'.format(var)
                for fn in fnames:
                    st += '{} : '.format(fn.ljust(colwidth))
                    if group in nmlall[fn]:
                        if var in nmlall[fn][group]:
                            st += repr(nmlall[fn][group][var])  # TODO: use f90repr
                    st += '\n'
    return st


def nml_md(nmlfnames):
    """
    Display table in a Jupter notebook of groups and variables in Fortran
    namelist files.

    Parameters
    ----------
    nmlfnames : str, tuple or list
        string, or tuple or list of any number of namelist file path strings.
        Repeated files are silently ignored.

    Returns
    -------
    None

    """
    from IPython.display import display, Markdown  # slow to load so do it here
    display(Markdown(strnmldict(nmldict(nmlfnames), format='md')))
    return None


def nmldiff_md(nmlfnames):
    """
    Display table in a Jupter notebook of semantic differences in groups and
    variables in Fortran namelist files.

    Parameters
    ----------
    nmlfnames : str, tuple or list
        string, or tuple or list of any number of namelist file path strings.
        Repeated files are silently ignored.

    Returns
    -------
    None

    """
    from IPython.display import display, Markdown  # slow to load so do it here
    display(Markdown(strnmldict(nmldiff(nmldict(nmlfnames)), format='md')))
    return None


if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=
        'Semantically tabulate (and optionally diff) multiple Fortran namelist files.\
        Undefined namelist variables are shown as blank.\
        Repeated files are silently ignored.\
        Latest version: https://github.com/aekiss/nmltab')
    parser.add_argument('-d', '--diff',
                        action='store_true', default=False,
                        help='only show semantic differences (default: show all); \
                        exit code 0: no differences; 1: differences')
    parser.add_argument('-p', '--prune',
                        action='store_true', default=False,
                        help='ignore all but the first in any sequence files with\
                        semantically indentical content')
    parser.add_argument('-i', '--ignore_counters',
                        action='store_true', default=False,
                        help='when doing --prune, ignore differences in timestep\
                        counters used in CICE and MATM namelists')
    parser.add_argument('-F', '--format', type=str,
                        metavar='fmt', default='str',
                        choices=['markdown', 'latex'],
                        help="alternative output format: \
                        'markdown' or 'latex'")
    parser.add_argument('--tidy_overwrite',
                        action='store_true', default=False,
                        help='OVERWRITE files with only their parsed contents \
                        (all comments are removed), \
                        with consistent formatting and sorted alphabetically \
                        by group then variable name \
                        (sorting requires https://github.com/marshallward/f90nml/pull/50). \
                        This makes standard diff much more useful.\
                        Files with no namelist data are left untouched. \
                        All other options are ignored. \
                        USE WITH CARE!')
    parser.add_argument('file', metavar='file', type=str, nargs='+',
                        help='Fortran namelist file')
    args = parser.parse_args()
    fmt = vars(args)['format']
    diff = vars(args)['diff']
    prune = vars(args)['prune']
    ignore = vars(args)['ignore_counters']
    tidy = vars(args)['tidy_overwrite']
    files = vars(args)['file']
    if prune and not tidy:
        nmld = nmldict(prunefilelist(files))
    else:
        nmld = nmldict(files)
    if tidy:
        tidy_overwrite(nmld)
    else:
        if diff:
            nmld = nmldiff(nmld)
        if prune:
            if ignore:
                nmld = nmlprune(nmld,
                                ignore={'setup_nml': ['istep0'],
                                        'coupling': ['inidate', 'truntime0']})
            else:
                nmld = nmlprune(nmld)
        nmldss = superset(nmld)
        if len(nmldss) == 0:
            sys.exit(0)
        else:
            print(strnmldict(nmld, format=fmt, masterswitch='use_this_module'),
                  end='', flush=True)
            if diff:
                sys.exit(1)
            else:
                sys.exit(0)
