
# neftox
An open source tool for creating highly-personalized, scientific and visually appealing presentation slides in a text editor.

### About
In the recent years, the author became increasingly frustrated with tools designed to create presentation slides. They are either expensive, not available for Linux, extremely awkward to use, unsupportive of scientific expressions and symbols, or do not provide enough flexibility for giving your presentation a personal touch. Often enough, more than one from that list.
But there exists a field that offers sheer unlimited possibilities for front-end arrangements, with tools that everyone can learn to use in a matter of days: Web design. So why not use it to create presentations?

The neftox tools is text-editor based (it does not come with a graphical interface), and requires basic knowledge of HTML and CSS scripting languages. It can understand LaTeX expressions for the creation of scientific content.

This tool is designed to combine the best from two worlds: The freedom and flexibility of web designing, with the possibilities of scientific document typesetting tools.


### Prerequisites

The following Python3 packages are required for neftox to work:

```
numpy
os
sys
re
subprocess
copy
matplotlib.font_manager
PIL
selenium
img2pdf
```

If you want to use LaTeX expressions in your presentation, you also need

```
sympy
```

as well as a working TeX Live installation. 

### Usage

```
./neftox.py <presentation dir> <option>
```

Available options:
```
--html        # Create browser output
--preview     # Create a preview with JPG images
--pdf         # Create PDF presentation
```

### Example slides

The following example slides have been created with the neftox tutorial:

<img src="./tutorial/parse/output_00.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_01.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_02.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_03.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_04.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_05.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_06.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_07.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_08.jpg" alt="example slide" width="100%"/>
<img src="./tutorial/parse/output_09.jpg" alt="example slide" width="100%"/>
