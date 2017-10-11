#!/usr/bin/env python3
"""

General-purpose tools to semantically tabulate, diff and superset Fortran namelist files.
Also includes a command-line interface.

Latest version: https://github.com/aekiss/nmltab
Author: Andrew Kiss https://github.com/aekiss
Apache 2.0 License http://www.apache.org/licenses/LICENSE-2.0.txt
"""

import f90nml  # from http://f90nml.readthedocs.io
import textwrap
import copy
import warnings
import collections
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
    nmlsuperset = {}
    for nml in nmlall:
        nmlsuperset.update(nmlall[nml])
    # nmlsuperset now contains all groups that were in any nml
    for group in nmlsuperset:
        # to avoid the next bit changing the original groups
        nmlsuperset[group] = nmlsuperset[group].copy()
        for nml in nmlall:
            if group in nmlall[nml]:
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


def rmcommonprefix(strlist):
    """
    Remove common prefix from a list of strings.

    Parameters
    ----------
    strlist: list of str
        non-empty list of strings

    Returns
    -------
    strlist: list of str
        list of strings with common prefix removed

    """
    i = 0  # needed for strlist of length 1 - python bug workaround?
    for i in range(0, min(len(s) for s in strlist)):
        if len(set(ss[i] for ss in strlist)) > 1:
            i = i - 1
            break
    return [s[(i+1):] for s in strlist]


def rmcommonsuffix(strlist):
    """
    Remove common suffix from a list of strings.

    Parameters
    ----------
    strlist: list of str
        non-empty list of strings

    Returns
    -------
    strlist: list of str
        list of strings with common suffix removed

    """
    for i in range(1, 1 + min(len(s) for s in strlist)):
        if len(set(ss[-i] for ss in strlist)) > 1:
            i = i - 1
            break
    if i == 0:
        return list(strlist)
    else:
        return [s[:(-i)] for s in strlist]


def strnmldict(nmlall, format=''):
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

    Returns
    -------
    string
        String representaion of nmlall.
        Default lists alphabetically by group, variable, then dict key,
        with undefined namelist variables shown as blank.

    """
    def latexstr(item):
        return item.replace('_', '\\_').replace('/', '\\slash ')

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
            % File auto-generated by nmltab.py <https://github.com/aekiss/nmltab>
            % Requires ltablex, array and sistyle packages
            % Also need to define 'nmldiffer' and 'nmllink' commands, e.g.
            % \\newcommand{\\nmldiffer}[1]{#1} % no special display of differing variables
            % \\newcommand{\\nmldiffer}[1]{\\textbf{#1}} % bold display of differing variables
            % \\definecolor{hilite}{cmyk}{0, 0, 0.9, 0}\\newcommand{\\nmldiffer}[1]{\\colorbox{hilite}{#1}}\\setlength{\\fboxsep}{0pt} % colour highlight of differing variables (requires color package)
            % \\newcommand{\\nmllink}[2]{#1} % don't link variables
            % \\newcommand{\\nmllink}[2]{\href{https://github.com/mom-ocean/MOM5/search?q=#2}{#1}} % link variables to documentation (requires hyperref package)
            % and also the length 'nmllen', e.g.
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
                    if i == 0:
                        gr = group
                    else:
                        gr = ''
                    st1 = '{} \\hfill \\nmllink{{{}}}{{{}}}'.format(
                        latexstr(gr), latexstr(var), var)
                    if group in nmldss:
                        if var in nmldss[group]:
                            st1 = '{} \\hfill \\nmllink{{\\nmldiffer{{{}}}}}{{{}}}'.format(
                                latexstr(gr), latexstr(var), var)
                    st += st1
                    for fn in fnames:
                        st += '\t & \t'
                        if group in nmlall[fn]:
                            if var in nmlall[fn][group]:
                                st += latexrepr(nmlall[fn][group][var])  # TODO: use f90repr
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
    parser.add_argument('-F', '--format', type=str,
                        metavar='fmt', default='str',
                        choices=['str', 'md', 'markdown', 'latex'],
                        help="alternative output format: \
                        'markdown' or 'latex'")
    parser.add_argument('file', metavar='file', type=str, nargs='+',
                        help='Fortran namelist file')
    args = parser.parse_args()
    fmt = vars(args)['format']
    diff = vars(args)['diff']
    files = vars(args)['file']
    nmld = nmldict(files)
    if diff:
        nmld = nmldiff(nmld)
    nmldss = superset(nmld)
    if len(nmldss) == 0:
        sys.exit(0)
    else:
        print(strnmldict(nmld, format=fmt), end='', flush=True)
        if diff:
            sys.exit(1)
        else:
            sys.exit(0)
