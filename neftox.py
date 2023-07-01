#!/usr/bin/env python3

import numpy as np
import os, sys
import re
import subprocess
import copy
import matplotlib.font_manager
from PIL import Image, ImageFont

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import img2pdf

#-- Global functions and variables -------------------------------------
global inputdir, parsedir, equdir

def MatchBetween(start, stop, string, len=1):
    ## Grab the content between two custom tags.
    pattern = '(?<={})\s*(.*?)\s*(?={})'.format(start, stop)
    matches = re.findall(pattern, string, flags=re.S|re.M)

    result = (matches if matches else ([] if len==None else[(None,)*len]))
    return result

def DeleteBracket(start, stop, string, replace=''):
    ## Deletes or replaces custom tags from a string.
    string = string.replace(start, replace)
    string = string.replace(stop, replace)
    return string

#-----------------------------------------------------------------------

class Presentation(object):

    regex_meta     = '([A-Z]*) *= *(.*)\n|\r'
    regex_style    = '\/\* palette PALETTE \*\/\s:root\s*{\n((.|\s)*?)}'
    regex_template = 'template_\d\d.html'

    def __init__(self, inputargs):

        self.dir = os.path.join(os.path.abspath(os.getcwd()), '')
        ## Re-start custom style file:
        if 'customs.css' in os.listdir('styles'):
            os.remove('styles/customs.css')

        ## Extract raw input content:
        global inputdir, parsedir, equdir
        inputdir = os.path.join(os.path.abspath(inputargs[1]), '')
        parsedir = os.path.join('{}parse'.format(inputdir), '')
        equdir = os.path.join(parsedir, 'equations', '')
        if not os.path.isdir(parsedir):
            os.mkdir(parsedir)
        if os.path.isdir(equdir):
            for equ in os.listdir(equdir):
                os.remove(equdir+equ)

        addargs  = inputargs[2:]
        with open(inputdir+'/input.html', 'r') as f:
            rawcontent = f.read()
        self.rawcontent = rawcontent

        self.ParseMeta()
        self.SetPalette()
        self.SetStyle()
        self.GetFrames()

    def ParseMeta(self):
        ## Default meta data:
        self.defaultmeta = {
            'STYLE'   : 'whimsical',
            'OFFSET'  : '0',
            'PALETTE' : 'tangerine',
            'FONT'    : 'nefcal',
            'FONTSIZE': '35px',
            'BROWSER' : 'firefox',
        }
        ## Parse the user meta data:
        meta = re.findall(
            Presentation.regex_meta,
            self.rawcontent.split('<!-- FRAME')[0]
        )
        for dkey, dvalue in self.defaultmeta.items():
            setattr(self, dkey, dvalue)
        for key, value in meta:
            setattr(self, key, value)

        self.FONTSIZE = float(self.FONTSIZE.rstrip('px'))

    def SetPalette(self):
        ## Writes the user-defined style options from the input file meta
        ## into a separate style sheet.

        ## Set palette. This copies the colors of the respective palette
        ## from palettes.css into customs.css and renames them, so that
        ## the stylesheet can call them without being messed with.
        with open('styles/palettes.css', 'r') as pf:
            palettes = pf.read()
        palette = re.search(
            Presentation.regex_style.replace('PALETTE', self.PALETTE),
            palettes
        ).group(1)

        colors = []
        for name, color in zip(
            ['box', 'text', 'color', 'highlight', 'back'],
            palette.split('--')[1:]
        ):
            colors.append((name, color.split(': ')[1].split(';')[0]))

        self.WriteStyle(':root', colors)

    def WriteStyle(self, bracket, styles, prefix='--'):
        ## Writes user-defined styles into a custom style sheet.
        placeholder = '    {}{}: {};\n'
        with open('styles/customs.css', 'a') as f:
            f.write('{} {{\n'.format(bracket))
            for name, value in styles:
                f.write(placeholder.format(prefix, name, value))
            f.write('}\n')

    def SetStyle(self):
        ## Read stylesheet:
        stylefile = 'styles/'+self.STYLE+'.css'
        with open(stylefile, 'r') as sf:
            stylesheet = sf.read()

        ## Extract style elements that are relevant for the frame layout
        ## on script level:
        elements = [
            ('fontfactor',    '--fontfactor: *(\d*.*\d*);'),
            ('totalwidth',    '--totalwidth: *(\d*)px;'),
            ('totalheight',   '--totalheight: *(\d*)px;'),
            ('boxmargin',     '--boxmargin: *(\d*)px;'),
            ('boxpadding',    '--boxpadding: *(\d*)px;'),
        ]
        styles = {}
        for el, regex in elements:
            el_ = re.search(regex, stylesheet)
            styles[el] = (el_.group(1) if el_ else '')

        self.styles = styles
        self.FindFont()

        ## Load the templates:
        templates = {}
        for templatefile in os.listdir('styles/templates/'):
            if re.fullmatch(Presentation.regex_template, templatefile):
                template = Template(templatefile)
                templates[template.name] = template

        ## Insert style sheet and meta info into templates:
        rules = [
            ('{STYLE}', '{}styles/{}.css'.format(self.dir, self.STYLE)),
            ('{TITLE}',  self.TITLE),
            ('{AUTHOR}', self.AUTHOR),
            ('{DATE}',   self.DATE),
        ]
        for name, template in templates.items():
            for rule in rules:
                template.content = template.content.replace(rule[0], rule[1])

        self.templates = templates

    def FindFont(self):
        ## Locate chosen font, and revert to default if not found:

        def LocateFontFile(fontname, size):

            regex_reg  = '{}([-_]*[rR](egular)*)*\.ttf'.format(fontname)
            regex_bold = '{}[-_]*[bB](old)*\.ttf'.format(fontname)

            systemfonts = matplotlib.font_manager.findSystemFonts()
            fontlist = [f for f in systemfonts if fontname in f]

            fonts = { 'regular': None, 'bold': None, 'path': None}
            for name in fontlist:
                if re.search(regex_reg, name):
                    fonts['regular'] = ImageFont.truetype(name, size)
                    fonts['path'] = name
                if re.search(regex_bold, name):
                    fonts['bold'] = ImageFont.truetype(name, size)

            return fonts

        fonts = LocateFontFile(
            self.FONT,
            int(float(self.FONTSIZE)*float(self.styles['fontfactor']))
        )
        try:
            assert fonts['regular'].getname()
        except:
            print('FONT not found, reverting to default font.')
            fonts = LocateFontFile(
                self.defaultmeta['FONT'],
                int(float(self.FONTSIZE)*float(self.styles['fontfactor']))
            )
            self.FONT = self.defaultmeta['FONT']

        ## The default font needs to be manually installed before first use:
        if self.FONT==self.defaultmeta['FONT'] and fonts['regular'] == None:
            print(
                '\nDefault font not found. If this is your first use, please '
                'install it from neftox/styles/fonts/\n.'
            )

        fonts['bold'] = (fonts['regular'] if not fonts['bold'] else fonts['bold'])

        self.WriteStyle(':root', [
            ('fontfamily', self.FONT),
            ('basesize', '{}px'.format(self.FONTSIZE)),
        ])

        ## Some fonts have to be enabled in the style sheet:
        self.WriteStyle('@font-face', [
                ('font-family', self.FONT),
                ('src', 'url(\'{}\')'.format(fonts['path'])),
            ],
            prefix = ''
        )

        self.fonts = fonts

    def GetFrames(self):
        ## Attributes that are being passed over to the frame class:
        passattr = [
            ('inputdir',  inputdir),
            ('styles',    self.styles),
            ('fonts',     self.fonts),
            ('templates', self.templates),
            ('OFFSET',    self.OFFSET),
        ]

        rawframes = self.rawcontent.split('<!-- FRAME ')[1:]
        frames    = {}
        for num, rf in enumerate(rawframes):
            frame = Frame(num, rf, passattr)
            frames[str(frame.number)] = frame

        self.frames = frames

        ## If a frame is a subframe, copy everything that is un-changed
        ## from the previous frame, and update the rest:
        for framenumber, frame in self.frames.items():
            if frame.KIND == 'subframe':
                prevframe = self.frames[str(frame.number-1)]
                subframe_ = copy.deepcopy(prevframe)
                allowed = frame.templates[frame.TEMPLATE].allowed

                ## Set meta information (if updated):
                for key, value in frame.__dict__.items():
                    if value and (key not in ['boxes']):
                        setattr(subframe_, key, value)

                ## Set content (if updated):
                for a in allowed:
                    if ((not frame.boxes[a].content) and
                    (not frame.boxes[a].style)):
                        pass
                    elif 'ADD--' in frame.boxes[a].content:
                        subframe_.boxes[a].UpdateContent(
                            frame.boxes[a].content
                        )
                    else:
                        subframe_.boxes[a] = frame.boxes[a]

                frame.__dict__ = subframe_.__dict__.copy()
            frame.ParseBackground()
            frame.InsertIntoTemplate()

    def CreateHTML(self):

        HTML = ''
        for framenumber, frame in self.frames.items():
            HTML += frame.HTML

        self.HTML = HTML

        with open(parsedir+'output.html', 'w') as pf:
            pf.write(self.HTML)

    def CreatePreview(self):
        ## Creating "screenshots" of the HTML preview pages using
        ## Selenium. Hoping to support different browers in the future.

        ## Determine window size:
        windowsize = {
            'width'  : int(self.styles['totalwidth']),
            'height' : int(self.styles['totalheight']),
        }

        ## Initiate web driver:
        if self.BROWSER in ['chrome', 'chromium']:
            print('Initializing Chrome driver ...')
            options = webdriver.chrome.options.Options()
            options.headless = True
            options.add_argument("--disable-extensions");
            options.add_argument("--hide-scrollbars");
            driver = webdriver.Chrome(
                options=options,
                # executable_path='/usr/bin/chromedriver'
            )
        else:
            print('Initializing Firefox driver ...')
            options = webdriver.firefox.options.Options()
            options.headless = True
            options.add_argument("--no-sandbox");
            options.add_argument("--disable-extensions");
            options.add_argument("--dns-prefetch-disable");
            driver = webdriver.Firefox(
                options=options,
                service_log_path=os.path.devnull
            )

        driver.set_window_size(windowsize['width'], windowsize['height'])
        url = 'file:///{}parse/output.html'.format(inputdir)
        driver.get(url)

        # Create test image. This is necessary to determine the size of
        # the nav bar/ overhead of the browser, which has to be taken
        # into account in the screenshot size. I could not find a better
        # way to solve this yet.
        testfile = '{}parse/test.png'.format(inputdir)
        driver.save_screenshot(testfile)
        scrolloffset = Image.open(testfile).height - windowsize['height']
        windowsize['height'] = windowsize['height']-scrolloffset
        driver.set_window_size(windowsize['width'], windowsize['height'])
        os.remove(testfile)

        print('Creating preview ...')
        imgfiles = []
        scroll = windowsize['height']+scrolloffset
        for f in range(len(self.frames)):
            png = '{}parse/output_{:02d}.png'.format(inputdir, f)
            driver.save_screenshot(png)
            driver.execute_script('window.scrollTo(0, '+str(scroll)+')')
            scroll += windowsize['height']+scrolloffset
            ## The following removes the alpha channels from the images,
            ## which is necessary for the pdf convert:
            command = 'convert {} -background white -alpha remove -alpha off {}'.format(png, png)
            call = subprocess.Popen([command], stdout=subprocess.PIPE, shell=True)
            (output, error) = call.communicate()
            ## Convert the images to jpg, which reduces size of output
            ## PDF significantly:
            jpg = png.replace('.png', '.jpg')
            imgfiles.append(jpg)
            Image.open(png).save(jpg, 'JPEG', optimize=True, quality=95)
            os.remove(png)

        driver.quit()
        self.imgfiles = list(np.sort(imgfiles))

    def CreatePDF(self):
        ## Convert images to PDF presentation, and delete preview.
        self.CreatePreview()

        print('Converting to PDF ...')

        outfile = '{}.pdf'.format(os.path.basename(os.path.normpath(inputdir)))
        with open(inputdir+outfile, 'wb') as f:
            f.write(img2pdf.convert(self.imgfiles))

        for imgfile in self.imgfiles:
            os.remove(imgfile)

        print('Done!')


class Template(object):

    regex_boxdefs  = '<!-- (BOX.*) -->'

    def __init__(self, filename):

        ## Read the file:
        with open('styles/templates/{}'.format(filename), 'r') as tf:
            content = tf.read()

        ## Identify possible content:
        boxes = re.search(Template.regex_boxdefs, content)
        boxes = boxes[1].split(', ')

        self.name    = filename.rstrip('.html')
        self.content = content
        self.allowed = boxes


class Frame(object):

    regex_comment      = '(<!--\s[\s\S]*?\s-->)'
    regex_meta         = '([A-Z|_]+) *= *(#?\w+.*)\s'
    regex_defaultstyle = '({(\w*) default} *(.*)\s)'

    pagecount = 0

    def __init__(self, number, rawframe, pres_attr):
        self.number    = number
        self.rawframe  = rawframe
        for name, pr in pres_attr:
            setattr(self, name, pr)

        self.CutComments()
        self.ParseMeta()
        self.ParseBackground()
        self.ParseContent()

    def CutComments(self):
        self.rawframe = re.sub(Frame.regex_comment, '', self.rawframe)

    def ParseMeta(self):
        ## Set default meta data:
        self.KIND     = 'frame'
        self.TEMPLATE = '00'
        ## Parse the user meta data:
        meta = re.findall(Frame.regex_meta, self.rawframe)
        for item in meta:
            setattr(self, item[0], item[1])

        self.TEMPLATE = 'template_'+self.TEMPLATE

        Frame.pagecount -= (int(self.OFFSET) if self.number==0 else 0)
        Frame.pagecount += (0 if self.KIND=='subframe' else 1)
        self.page = Frame.pagecount

    def ParseBackground(self):
        ## The frame background can be specified as a css statement with
        ## the BACKGROUND meta key word. A plain color or an image in the
        ## default image folder can also be specified with the shortcut
        ## keywords BACKGROUND_COLOR or BACKGROUND_IMG.
        rules = [
            ('BACKGROUND',       '{}'),
            ('BACKGROUND_IMG',   'background-image: url(../pictures/{}); '),
            ('BACKGROUND_COLOR', 'background-color: {}; '),
        ]
        placeholder = '<div class="background" style="{background}"></div>\n'
        background  = placeholder.replace(' style="{background}"', '')
        for key, value in rules:
            if key in dir(self):
                background += placeholder.replace(
                    '{background}',
                    value.format(getattr(self, key))
                )
        self.background = background

    def ParseContent(self):
        ## Extract content information for each frame:

        boxes = {}
        for a in self.templates[self.TEMPLATE].allowed:
            match_ = MatchBetween(
                '({})--'.format(a), '--{}'.format(a), self.rawframe, 2
            )[0]
            if match_[0]:
                rawbox = match_
            else:
                rawbox = [a, match_[1]]
            boxes[a] = Box(
                rawbox, self.templates[self.TEMPLATE], self.number
            )

        self.boxes = boxes

    def InsertIntoTemplate(self):

        HTML = self.templates[self.TEMPLATE].content
        ## Insert page number and background:
        HTML = HTML.replace('{page}', '{}'.format(self.page))
        HTML = HTML.replace('{background}', '{}'.format(self.background))

        ## Determine width of title (used in some templates):
        if 'BOXTITLE' in self.boxes.keys():
            titlewidth = self.fonts['bold'].getlength(
                ' {} '.format(self.boxes['BOXTITLE'].content)
                # ' {} '.format(self.boxes['BOXTITLE'].content)
            )
            titlewidth += 2*int(self.styles['boxpadding'])
            self.boxes['BOXTITLE'].SetStyle([('width', '{}px'.format(titlewidth))])
        else:
            titlewidth = 0
        HTML = HTML.replace('{titlewidth}', '{}'.format(titlewidth))

        ## Some boxes can have default styles with values that can only
        ## be set on run-time (e.g. in case the width of a box depends
        ## on the content of another). Those default values are parsed
        ## here:
        defaults = re.findall(Frame.regex_defaultstyle, HTML)
        for df in defaults:
            HTML = HTML.replace(df[0], '')
            for boxname, box in self.boxes.items():
                if box.name == df[1]:
                    box.SetStyle([eval(df[2])])

        for boxname, box in self.boxes.items():
            HTML = HTML.replace('{{{} style}}'.format(box.name), box.style)
            HTML = HTML.replace('{{{}}}'.format(box.name), box.content)

        self.HTML = HTML


class Box(object):

    re_style = '^\s*style *= *\"(.*)\" *'
    re_li    = '(<li((.|\s)*?)<\/li>)'

    def __init__(self, rawbox, template, framenumber):
        self.name     = rawbox[0]
        self.style    = ''
        self.template = template
        self.frame    = framenumber

        self.ParseContent(rawbox[1])

        if not self.name=='BOXFOOTER':
            self.Appear()

    def SetStyle(self, styles):
        ## Append new style commands to the existing style string.

        newstyles = set()
        ## The styles argument can be passed as a tuple of a css keyword
        ## and value (clean) or as a string (dirty). The string has to
        ## be tuple'd first, this happens below:
        for s_ in styles:
            if isinstance(s_, tuple):
                newstyles.add(s_)
            elif isinstance(s_, str):
                list_ = list(filter(None, s_.split(';')))
                for l in list_:
                    newstyles.add(tuple(l.split(':')))
            else:
                newstyles.add((None,))

        result = self.style.lstrip('style="').rstrip('"')
        for key, value in newstyles:
            result += ' {}: {};'.format(key, value)

        result = 'style="{}"'.format(result)
        self.style = result

    def ParseContent(self, rawcontent):

        ## Check for ... well, content:
        if not rawcontent:
            self.content = ''
            return
        else:
            content = rawcontent

        ## Check for styles:
        style_ = re.search(Box.re_style.format(self.name), rawcontent)
        if style_:
            self.SetStyle([style_.group(1)])
            content = rawcontent.replace(style_.group(0), '')

        ## Check for equations::
        eqcount = 0
        equs_ = MatchBetween(*Equation.re_brackets, content, None)
        equs = []
        for e in equs_:
            equ = Equation(e, self.frame, self.name, eqcount)
            content = content.replace(e, equ.HTML)
            eqcount += 1

        content = DeleteBracket(*Equation.re_brackets, content)
        content = content.strip('\n').strip(' ')
        self.content = content

    def UpdateContent(self, newcontent, rev=False):

        if rev == True:
            first, second = newcontent, self.content.replace('ADD--', '')
        else:
            first, second = self.content, newcontent.replace('ADD--', '')

        lis = re.findall(Box.re_li, second)
        liobj = ' '.join(li[0] for li in lis)
        if lis and ('</ul>' in first):
            third = first.replace('</ul>', '{}\n</ul>'.format(liobj))
        elif lis and ('</ol>' in first):
            third = first.replace('</ol>', '{}\n</ol>'.format(liobj))
        else:
            third = first + second

          # li = s.rsplit(old, occurrence)
          # return new.join(li)

        self.content = third

    def Appear(self):
        ## Boxes are hidden by default. This makes them visible.
        if self.style or self.content:
            self.SetStyle([('visibility', 'visible')])


class Equation(object):

    re_brackets = ('TEX--', '--TEX')

    def __init__(self, rawtex, framenumber, boxname, count):

        if not os.path.isdir(equdir):
            os.mkdir(equdir)

        self.rawtex = rawtex
        self.name   = '{:02d}-{}-{:02d}'.format(framenumber, boxname, count)
        self.eqpath = '{}{}.png'.format(equdir, self.name)

        self.Eqtopng()
        self.EqtoHTML()

    def Eqtopng(self):
        ## Converts latex expression to png image.

        from sympy import preview

        # preamble = (
        #     # '\\documentclass[35pt]{article}\n'
        #     '\\documentclass[tikz]{standalone}\n'
        #     # '\\usepackage[fontsize=10.8pt]{fontsize}'
        #     '\\usepackage{units}'
        #     '\\usepackage{newpxtext}'
        #     '\\usepackage{newpxmath}'
        #     '\\usepackage{xcolor}'
        #     '\\begin{document}'
        # )

        packages = (
            'units',
            'lmodern',
            # 'newpxtext', 'newpxmath',
            'xcolor',
        )
        ## Scale the image by a factor to get decent resolution:
        scale = 4
        dvioptions = [
            '-D {}'.format(scale*100),
            '-bg', 'rgb 20 20 20',
            '-bd', '100', '--gamma', '10'
        ]
        preview(
            self.rawtex, viewer='file', filename=self.eqpath,
            dvioptions=dvioptions, euler=False,
            packages=packages,
            # preamble=preamble,
        )
        self.dims = np.array(Image.open(self.eqpath).size)/scale

    def EqtoHTML(self):

        re_subchars = r'\b(?<![\\|{])\w*[gjpqy]\w*\b'

        subgreeks = [
            'beta ', 'gamma ', 'zeta ', 'mu ', 'xi ', 'rho ', 'varrho ',
            'varsigma ', 'phi ', 'varphi ', 'chi ', 'psi ',
        ]

        offset = ''
        ## Check if expression is one-liner:
        if self.dims[1] < 100:
            ## Check if expression contains regular words with
            ## descendent characters, or descendent greek symbols:
            test1 = re.search(re_subchars, self.rawtex)
            test2 = any('\\{}'.format(char) in self.rawtex for char in subgreeks)
            if test1 or test2:
                offset = 'margin-bottom: -{}px;'.format(self.dims[1]*0.24)

        self.HTML = '<img src="{}" style="width:{}px; {}"/>\n'.format(
            self.eqpath, self.dims[0], offset,
        )


#--- Parse arguments ---------------------------------------------------

def CheckArguments(args):
    try:
        assert 'input.html' in os.listdir(sys.argv[1])
        for arg in sys.argv[2:]:
            assert arg in [item for sublist in possargs for item in sublist]
        pass
    except:
        print('\nUsage:\n./neftox.py <presentation directory> [optional args]\n')
        raise ValueError('Bad or wrong number of arguments.')

#--- Make it so! -------------------------------------------------------
possargs = [
    ['--html', '--HTML'],
    ['--preview'],
    ['--pdf', '--PDF'],
]

CheckArguments(sys.argv)
pres = Presentation(sys.argv)

if sys.argv[2] in ['--html', '--HTML']:
    pres.CreateHTML()
if sys.argv[2] in ['--preview']:
    pres.CreateHTML()
    pres.CreatePreview()
if sys.argv[2] in ['--pdf', '--PDF']:
    pres.CreateHTML()
    pres.CreatePDF()
