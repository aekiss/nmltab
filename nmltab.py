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
# sys.path.insert(0, '/Users/andy/Documents/COSIMA/github/aekiss/f90nml') # BUG: doesn't work with /Users/andy/anaconda/bin/python3 /Users/andy/bin/nmltab.py --fmt latex    new/control/025deg_jra55_ryf/ice/input_ice_gfdl.nml

import f90nml  # from http://f90nml.readthedocs.io
import sys
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
        If a file contains repeated groups, only the first instance is used.

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
    for nml in nmlall:
        for group in nmlall[nml]:
            if isinstance(nmlall[nml][group], list):
                # A list indicates group is defined more than once in nml file.
                # The list contains the groups in order of occurrence.
                # For the nth group's values to have any effect in f90,
                # the namelist needs to be read n times from the input file,
                # without closing the file in between.
                # If the same variable name occurs in multiple instances of 
                # the same group, the last read instance is used.
                # Since we don't know how many times the group is read in f90, 
                # ignoring all but the first seems the safest option.
                # TODO: provide an option to consolidate all groups in list?
                warnings.warn('&{} occurs {} times in {}. Using only the first instance of this group.'.format(group, str(len(nmlall[nml][group])), nml))
                nmlall[nml][group] = nmlall[nml][group][0]
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
                nmlsuperset[group].update(nmlall[nml][group])
    # nmlsuperset groups now contain all keys that were in any nml
    return nmlsuperset


def nmldiff(nmlall, keep=''):
    """
    In-place remove every group/variable that's the same in all file Namelists.

    Parameters
    ----------
    nmlall : dict or OrderedDict
        dict (e.g. returned by nmldict) with `key`:`value` pairs where
        `key` is arbitrary (typically a filename path string)
        `value` is Namelist (typically from filename via f90nml.read)
    keep : variable name
        variable name to always keep in diff, unless the group has no differences

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
        varkept = False  # whether var is kept when it would otherwise be deleted
        onlyvarkept = False  # whether var is kept and is the only var in this group across all nmls
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
                        if var == keep:
                            varkept = True
                        else:
                            for nml in nmlall:
                                # delete var from this group in all nmls
                                del nmlall[nml][group][var]
            if varkept:
                onlyvarkept = True
                for nml in nmlall:
                    onlyvarkept = onlyvarkept and len(nmlall[nml][group]) < 2
                    if onlyvarkept and len(nmlall[nml][group]) == 1:
                        onlyvarkept = list(nmlall[nml][group].keys())[0] == keep
            if onlyvarkept:
                deletegroup = True
            else:
                deletegroup = max([len(nmlall[nml][group]) for nml in nmlall]) == 0
            if deletegroup:
                # group is common to all nmls and now empty (or only holding keep) so delete
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

    ignore : dict, optional, default={}
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


def tidy_overwrite(nmlall, colwidth=None):
    """
    Overwrite namelist files with parsed namelist data from those files,
    sorted alphabetically by group then variable name.
    Files with no namelist data are left untouched.

    Parameters
    ----------
    nmlall : dict or OrderedDict
        dict (e.g. returned by nmldict) with `key`:`value` pairs where
            `key` is filename path string to be overwritten
            `value` is Namelist (typically from filename via f90nml.read)
        colwidth: minimum width of column from start of variable name to
            start of " = ". If None, automatically uses longest variable name.

    Returns
    -------
    None

    """
    for nml in nmlall:
        if len(nmlall[nml]) > 0:
            if colwidth is None:
                colwidth = max([max([len(v) for v in list(g.keys())], default=0)
                                for g in list(nmlall[nml].values())], default=0)
            nmlout = nml + '-tmp'
            try:
                f90nml.write(nmlall[nml], nmlout, sort=True, colwidth=colwidth)
                os.replace(nmlout, nml)
            except:  # TODO: don't use bare except
                warnings.warn("Error {} tidying '{}'; file left untouched. \
Delete part-converted file '{}' before trying again."
                              .format(sys.exc_info()[0], nml, nmlout))
    return None


def strnmldict(nmlall, fmt='', masterswitch='', hide={}, heading='', url=''):
    """
    Return string representation of dict of Namelists.

    Parameters
    ----------
    nmlall : dict or OrderedDict
        dict (e.g. returned by nmldict) with `key`:`value` pairs where
        `key` is arbitrary (typically a filename path string)
        `value` is Namelist (typically from filename via f90nml.read)

    fmt : str, optional, case insensitive, default=''
        'md' or 'markdown': markdown string output
        'latex': latex string output (table only, suitable as an input file)
        'latex-complete': latex string, suitable for a complete .tex file
        'text': text output ([*] &group variable [value] file)
        'text-tight': as for 'text', but without aligned columns
        anything else: standard string output (different from 'text')

    masterswitch : str, optional, case insensitive, default=''
        key with boolean value that disables other variables in group
        if present and false, e.g. 'use_this_module' in MOM.
        NB: this key might be absent in namelist differences.
        Only used for fmt='latex' or 'latex-complete'.

    hide : dict, optional, default={}
        dict specifying namelist variables that will not be shown in output.
        key is namelist group
        value is a list of variable names within that group
        Ignored for fmt='md' or 'markdown'.
        TODO: implement for all formats

    heading : string, optional, default=''
        string to be written above table if fmt='latex-complete'

    url : string, optional, default=''
        url prefix for hyperlinked variables and groups if fmt='latex-complete'
        url='' (the default) has no hyperlinks

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

    # TODO: fail on unknown fmt
    # TODO: put data format in Fortran syntax eg for booleans and arrays - does nf90nml do this?
    #    - see f90repr in namelist.py: https://github.com/marshallward/f90nml/blob/master/f90nml/namelist.py#L405
    fmt = fmt.lower()
    nmlss = superset(nmlall)
    nmldss = superset(nmldiff(copy.deepcopy(nmlall)))  # avoid in-place modification
    fnames = list(nmlall.keys())
    colwidth = max((len(f) for f in fnames), default=0)  # default keyword requires Python 3.4 or later
    # TODO: test if the following works in python pre- and post-3.4
    # colwidth = max([len(f) for f in fnames] or [0])  # defaults to 0 if fnames is empty list, since empty list evaluates to False

    # TODO: would be faster & more efficient to .append a list of strings
    # and then join them:
    # http://docs.python-guide.org/en/latest/writing/structure/#mutable-and-immutable-types
    st = ''
    if fmt in ('md', 'markdown'):
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
    elif fmt.startswith('latex'):
        if len(nmlss) > 0:
            if fmt == 'latex':
                st += textwrap.dedent(r"""
                % Latex tabulation of Fortran namelist, auto-generated by nmltab.py <https://github.com/aekiss/nmltab>
                %
                % Include this file in a latex document using \import{path/to/this/file}.
                % The importing document requires
                % \usepackage{ltablex, array, sistyle}
                % and possibly (depending on definitions below)
                % \usepackage{hyperref, color}
                % and also needs to define 'nmldiffer', 'nmllink' and 'ignored' commands, e.g.
                % \newcommand{\nmldiffer}[1]{#1} % no special display of differing variables
                % \newcommand{\nmldiffer}[1]{\textbf{#1}} % bold display of differing variables
                % \definecolor{hilite}{cmyk}{0, 0, 0.9, 0}\newcommand{\nmldiffer}[1]{\colorbox{hilite}{#1}}\setlength{\fboxsep}{0pt} % colour highlight of differing variables (requires color package)
                % \newcommand{\nmllink}[2]{#1} % don't link variables
                % \newcommand{\nmllink}[2]{\href{https://github.com/mom-ocean/MOM5/search?q=#2}{#1}} % link variables to documentation (requires hyperref package)
                % \newcommand{\ignored}[1]{#1} % no special display of ignored variables
                % \definecolor{ignore}{gray}{0.7}\newcommand{\ignored}[1]{\textcolor{ignore}{#1}} % gray display of ignored variables (but only in groups where masterswitch key is present and false, so may not work well for differences; requires color package)
                % and also define the length 'nmllen' that sets the column width, e.g.
                % \newlength{\nmllen}\setlength{\nmllen}{12ex}

                """)
            elif fmt == 'latex-complete':
                st = textwrap.dedent(r"""    % generated by https://github.com/aekiss/nmltab
                \documentclass[10pt]{article}
                \usepackage[a4paper, truedimen, top=2cm,bottom=2cm,left=2cm,right=2cm]{geometry}

                \usepackage{PTSansNarrow} % narrow sans serif font for urls
                \usepackage[scaled=.9]{inconsolata} % for texttt
                \renewcommand{\familydefault}{\sfdefault}

                \usepackage[table,dvipsnames]{xcolor}    % loads also colortbl
                \definecolor{lightblue}{rgb}{0.93,0.95,1.0}  % for table rows
                \rowcolors{1}{lightblue}{white}
                \definecolor{link}{rgb}{0,0,1}
                \usepackage[colorlinks, linkcolor={link},citecolor={link},urlcolor={link},
                 breaklinks, bookmarks, bookmarksnumbered]{hyperref}
                \usepackage{url}
                \usepackage{breakurl}
                \urlstyle{sf}

                \usepackage{ltablex}\keepXColumns
                \usepackage{array, sistyle}

                \usepackage[strings]{underscore} % allows hyphenation at underscores
                \usepackage{datetime2}\DTMsetdatestyle{iso}

                \usepackage{makeidx}
                \makeindex

                \usepackage{fancyhdr}
                \pagestyle{fancy}
                \renewcommand{\headrulewidth}{0pt}
                \lfoot{{\footnotesize \textsl{Fortran namelist table generated by \url{https://github.com/aekiss/nmltab}}}}
                \rfoot{\textsl{\today\ \DTMcurrenttime\ \DTMcurrentzone}}

                \begin{document}

                \definecolor{ignore}{gray}{0.7}\newcommand{\ignored}[1]{\textcolor{ignore}{#1}} % gray display of ignored variables (but only in groups where masterswitch key is present and false, so may not work well for differences; requires color package)
                \newlength{\nmllen}\setlength{\nmllen}{12ex}

                """)
                st += heading
                if url is '':
                    st += r'\newcommand{\nmllink}[2]{#1\index{#1}}'
                else:
                    st += 'Variables are weblinks to source code searches.\n'
                    st += r'\newcommand{\nmllink}[2]{\href{' + url + r'#2}{#1}\index{#1}}'
                st += '\n'
            # TODO: get this use case working: 
            # % \definecolor{hilite}{cmyk}{0, 0, 0.9, 0}\newcommand{\nmldiffer}[1]{\rowcolor{hilite}#1} % colour highlight of rows with differing variables (requires xcolor package) BUG: DOESN'T WORK! Misplaced \noalign due to leading \hfill (and namelist group name if at start of group)
            st += '\\newcolumntype{R}{>{\\raggedleft\\arraybackslash}b{\\nmllen}}\n'
            st += '\\begin{tabularx}{\\linewidth}{X' + 'R' * len(fnames) + '}\n'
            st += '\\hline\n\\hiderowcolors\n'
            st += '\\textbf{Group\\quad\\hfill Variable}'
            # for fn in rmcommonprefix(rmcommonsuffix(fnames)):
            for fn in fnames:
                st += '\t & \t\\textbf{' + latexstr(fn) + '}'
            st += ' \\\\\n\\showrowcolors\n\\hline\\endfirsthead\n'
            st += '\\hline\n\\hiderowcolors\n'
            st += '\\textbf{Group (continued)\\quad\\hfill Variable}'
            # for fn in rmcommonprefix(rmcommonsuffix(fnames)):
            for fn in fnames:
                st += '\t & \t\\textbf{' + latexstr(fn) + '}'
            st += ' \\\\\n\\showrowcolors\n\\hline\\endhead\n'
            for group in sorted(nmlss):
                firstvar = True
                for var in sorted(nmlss[group]):
                    if not ((group in hide) and (var in hide[group])):
                        if firstvar:  # only show group once
                            gr = '\\&\\nmllink{{{}}}{{{}}}'.format(
                                latexstr(group), group)
                            firstvar = False
                        else:
                            gr = ''
                        st1 = '{} \\hfill \\nmllink{{{}}}{{{}}}'.format(
                            gr, latexstr(var), var)  # replaced below if differences
                        if group in nmldss:
                            if var in nmldss[group]:  # new st1 if differences
                                st1 = '{} \\hfill \\nmldiffer{{\\nmllink{{{}}}{{{}}}}}'.format(
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
                if not firstvar:
                    st += '\\hline\n'
            st += '\\end{tabularx}\n'
            if fmt == 'latex-complete':
                st += textwrap.dedent(r"""
                \clearpage
                \phantomsection % fix hyperrefs to index
                \addcontentsline{toc}{part}{\indexname}
                \printindex
                \end{document}
                """)
    elif fmt.startswith('text'):
        if fmt == 'text':
            gwidth = max([len(g) for g in list(nmlss.keys())], default=0)
            vwidth = max([max([len(v) for v in list(g.keys())], default=0)
                          for g in list(nmlss.values())], default=0)
            dwidth = max([
                        max([max([len(repr(v)) for v in list(g.values())], default=0)
                          for g in list(nmlall[fn].values())], default=0)
                          for fn in nmlall.keys()], default=0)
        else:  # assumes text-tight - TODO: be more stringent
            gwidth = 0
            vwidth = 0
            dwidth = 0
        for group in sorted(nmlss):
            for var in sorted(nmlss[group]):
                if not ((group in hide) and (var in hide[group])):
                    st1 = '  '
                    if group in nmldss:
                        if var in nmldss[group]:  # star if differences
                            st1 = '* '
                    for fn in fnames:
                        st += st1 + '&' + group.ljust(gwidth) + '  ' + var.ljust(vwidth) + '  '
                        dstr = ''
                        if group in nmlall[fn]:
                            if var in nmlall[fn][group]:
                                dstr = repr(nmlall[fn][group][var])  # TODO: use f90repr
                        st += dstr.ljust(dwidth) + '  ' + fn + '\n'
    else:
        for group in sorted(nmlss):
            for var in sorted(nmlss[group]):
                if not ((group in hide) and (var in hide[group])):
                    st += ' ' * (colwidth + 2) + '&{}\n'.format(group)
                    st += ' ' * (colwidth + 2) + ' {}\n'.format(var)
                    for fn in fnames:
                        st += '{} : '.format(fn.ljust(colwidth))
                        if group in nmlall[fn]:
                            if var in nmlall[fn][group]:
                                st += repr(nmlall[fn][group][var])  # TODO: use f90repr
                        st += '\n'
    return st


def nml_md(nmlfnames, diff=False, prune=False,
           ignore={'setup_nml': ['istep0'],
                   'coupling': ['inidate', 'truntime0']}):
    """
    Display table in a Jupter notebook of groups and variables in Fortran
    namelist files.

    Parameters
    ----------
    nmlfnames : str, tuple or list
        string, or tuple or list of any number of namelist file path strings.
        Repeated files are silently ignored.

    diff : boolean, optional, default=False
        just display semantic differences

    prune : boolean, optional, default=False
        just display the first file in which each variable change occurs

    ignore : dict, optional,
        default={'setup_nml': ['istep0'], 'coupling': ['inidate', 'truntime0']}
        variable names to ignore differences in if prune=True

    Returns
    -------
    None

    """
    from IPython.display import display, Markdown  # slow to load so do it here
    if prune:
        nmld = nmldict(prunefilelist(nmlfnames))
    else:
        nmld = nmldict(nmlfnames)
    if diff:
        nmldiff(nmld)
    if prune:
        nmlprune(nmld, ignore=ignore)
    display(Markdown(strnmldict(nmld, fmt='md')))
    return None


# def nmldiff_md(nmlfnames):
#     """
#     Display table in a Jupter notebook of semantic differences in groups and
#     variables in Fortran namelist files.
# 
#     Parameters
#     ----------
#     nmlfnames : str, tuple or list
#         string, or tuple or list of any number of namelist file path strings.
#         Repeated files are silently ignored.
# 
#     Returns
#     -------
#     None
# 
#     """
#     from IPython.display import display, Markdown  # slow to load so do it here
#     display(Markdown(strnmldict(nmldiff(nmldict(nmlfnames)), fmt='md')))
#     return None


if __name__ == '__main__':
    import argparse
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
                        help='ignore all but the first in any sequence of files \
                        with semantically indentical content')
    parser.add_argument('-i', '--ignore_counters',
                        action='store_true', default=False,
                        help='when doing --prune, ignore differences in timestep\
                        counters etc in CICE and MATM namelists, and also hide\
                        them from output (ignored for markdown output)')
    parser.add_argument('-k', '--keep', type=str,
                        metavar='str', default='',
                        help="variable to always keep in diff, unless it's the\
                        only one in a group, e.g. 'use_this_module'")
    parser.add_argument('-F', '--format', type=str,
                        metavar='fmt', default='str',
                        choices=['markdown', 'latex', 'latex-complete',
                                 'text', 'text-tight'],
                        help="optional alternative output format: \
                        'markdown' or 'latex' (table only, suitable as an \
                        input file) or 'latex-complete' (a complete .tex file) \
                        or 'text' (plain text; with each row row showing \
                        [*] &group variable [value] file) \
                        or 'text-tight' (like 'text', but without aligned columns)")
    parser.add_argument('-u', '--url', type=str,
                        metavar='url', default='',
                        help="link all variable and group names to this \
                        URL followed by the variable/group name, e.g. \
                        https://github.com/COSIMA/libaccessom2/search?q=")
    parser.add_argument('--tidy_overwrite',
                        action='store_true', default=False,
                        help='OVERWRITE files with only their parsed contents \
                        (all comments and non-namelist content are removed), \
                        with consistent formatting and sorted alphabetically \
                        by group then variable name. \
                        This makes standard diff much more useful. \
                        Files with no namelist data are left untouched. \
                        All other options are ignored. \
                        USE WITH CARE!')
    parser.add_argument('file', metavar='file', type=str, nargs='+',
                        help='Fortran namelist file')
    args = parser.parse_args()
    fmt = vars(args)['format']
    url = vars(args)['url']
    keep = vars(args)['keep']
    diff = vars(args)['diff']
    prune = vars(args)['prune']
    ignore = vars(args)['ignore_counters']
    tidy = vars(args)['tidy_overwrite']
    files = vars(args)['file']
    if prune and ignore:
        ignored = {'setup_nml': ['istep0'], #, 'npt', 'restart', 'runtype'],
                   'coupling': ['inidate', 'runtime', 'truntime0']}
    else:
        ignored = {}
    if prune and not tidy:
        nmld = nmldict(prunefilelist(files))
    else:
        nmld = nmldict(files)
    if tidy:
        tidy_overwrite(nmld, colwidth=17)
    else:
        if diff:
            nmldiff(nmld, keep=keep)
        if prune:
            nmlprune(nmld, ignore=ignored)
        nmldss = superset(nmld)
        if len(nmldss) == 0:
            sys.exit(0)
        else:
            if fmt == 'latex-complete':
                if diff:
                    heading = textwrap.dedent(r"""
                        \newcommand{\nmldiffer}[1]{#1} % no special display of differing variables
                        \noindent Only differences are shown.
                        \ignored{Greyed values} are ignored.
                        """)
                else:
                    heading = textwrap.dedent(r"""
                        \definecolor{hilite}{cmyk}{0, 0, 0.9, 0}\newcommand{\nmldiffer}[1]{\colorbox{hilite}{#1}}\setlength{\fboxsep}{0pt}
                        \noindent Variables that differ between the namelists are \nmldiffer{\textcolor{link}{highlighted}}.
                        \ignored{Greyed values} are ignored.
                        """)
                print(strnmldict(nmld, fmt=fmt, masterswitch='use_this_module',
                                 hide=ignored, heading=heading, url=url),
                      end='', flush=True)
            else:
                print(strnmldict(nmld, fmt=fmt, masterswitch='use_this_module',
                                 hide=ignored),
                      end='', flush=True)
            if diff:
                sys.exit(1)
            else:
                sys.exit(0)
