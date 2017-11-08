# nmltab

Python 3 module and command-line tool to tabulate, semantically diff, superset and consistently format Fortran namelist files, with output to text, markdown, latex and namelists.

Requires [f90nml](https://github.com/marshallward/f90nml) (amongst other packages).

## Why should I care?

Standard unix `diff` is not much use for comparing Fortran namelists, because two namelists can be equivalent even though they have differences in whitespace, capitalisation, variable order, and representation of values. 
In contrast, `nmltab.py -d` will show you only the differences that matter to Fortran. Other options and multiple output formats are also provided - see examples.

## Usage examples

### Command line
```
nmltab.py -h
```
Provides usage information.

```
nmltab.py file1.nml file2.nml ... fileN.nml
```
Shows all groups and variables in these namelist files, listed alphabetically.

```
nmltab.py -d file1.nml file2.nml ... fileN.nml
```
Shows only the semantic differences between the namelist files.

```
nmltab.py --format markdown file1.nml file2.nml ... fileN.nml
```
Shows all groups and variables in these namelist files, in markdown.

```
nmltab.py -d --format markdown file1.nml file2.nml ... fileN.nml
```
Shows only the semantic differences between the namelist files, in markdown.

```
nmltab.py --format latex file1.nml file2.nml ... fileN.nml > nml.tex
```
Creates latex file `nml.tex` containing a table of all groups and variables in the namelist files (and highlighting semantic differences), which can be read in by `\input{nml.tex}` (but see the comments at the start of `nml.tex` for the packages and command definitions required).

```
nmltab.py -h --format latex file1.nml file2.nml ... fileN.nml > nml.tex
```
Creates latex file `nml.tex` containing a table of all semantic differences between the namelist files, which can be read in by `\input{nml.tex}` (but see the comments at the start of `nml.tex` for the packages and command definitions required).

If you'd rather not have the intermediate `nml.tex` file you can tablulate namelists directly from within latex (and automatically update the table whenever the latex is typeset) via
```latex
\input{|"/path/to/python3 /path/to/nmltab.py --format latex file1.nml file2.nml ... fileN.nml"}
```
or to only show differences:
```latex
\input{|"/path/to/python3 /path/to/nmltab.py -h --format latex file1.nml file2.nml ... fileN.nml"}
```
This requires shell escape to be enabled, e.g. via `-shell-escape` in TeXlive; this is a security hole: only typeset files you trust!

```
nmltab.py --tidy_overwrite file1.nml file2.nml ... fileN.nml
```
**Overwrites** existing files with only their parsed contents
(all comments are removed),
with consistent formatting and alphabetically sorted 
by group then variable name
(sorting requires https://github.com/marshallward/f90nml/pull/50).
This makes standard `diff` much more useful on these files.
Files with no namelist data are left untouched.
**USE WITH CARE!**

### Jupyter notebook
```python
import nmltab
```
```python
nmltab.nml_md(['file1.nml', 'file2.nml', 'file3.nml'])
```
Displays a  markdown table of the contents of file1.nml, file2.nml, file3.nml. Any number of files can be given.
```python
nmltab.nmldiff_md(['file1.nml', 'file2.nml', 'file3.nml'])
```
Displays a  markdown table of the semantic differences between file1.nml, file2.nml, file3.nml. Any number of files can be given.


### Python
```python
import nmltab
```
```python
nmltab.nmldict(['file1.nml', 'file2.nml', 'file3.nml'])
```
Returns an OrderedDict of Namelists of the contents of file1.nml, file2.nml, file3.nml. Any number of files can be given. 
```python
nmltab.nmldiff(nmltab.nmldict(['file1.nml', 'file2.nml', 'file3.nml']))
```
Returns an OrderedDict of Namelists of the differences between file1.nml, file2.nml, file3.nml. Any number of files can be given. 
```python
nmltab.superset(nmltab.nmldict(['file1.nml', 'file2.nml', 'file3.nml']))
```
Returns a Namelists of every group and variable that occurs in any of file1.nml, file2.nml, file3.nml. Any number of files can be given. 


## Author
Andrew Kiss <https://github.com/aekiss>


## License
`nmltab` is distributed under the [Apache 2.0 License](http://www.apache.org/licenses/LICENSE-2.0.txt).

