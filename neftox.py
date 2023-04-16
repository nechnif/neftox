#!/usr/bin/env python3

import numpy as np
import os, sys
import re
import subprocess
import copy
import matplotlib.font_manager
from PIL import ImageFont

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import img2pdf


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
        self.inputdir = os.path.join(os.path.abspath(inputargs[1]), '')
        self.parsedir = os.path.join('{}parse'.format(self.inputdir), '')
        addargs  = inputargs[2:]
        with open(self.inputdir+'/input.html', 'r') as f:
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

        fonts['bold'] = (fonts['regular'] if not fonts['bold'] else fonts['bold'])

        self.WriteStyle(':root', [
            ('fontfamily', self.FONT),
            ('basesize', '{}px'.format(self.FONTSIZE)),
        ])

        # ## Some fonts have to be enabled in the style sheet:
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
            ('styles',    self.styles),
            ('fonts',     self.fonts),
            ('templates', self.templates),
        ]

        rawframes = self.rawcontent.split('<!-- FRAME ')[1:]
        frames    = {}
        for num, rf in enumerate(rawframes):
            frame = Frame(num+int(self.OFFSET), rf, passattr)
            frames[str(frame.number)] = frame

        self.frames = frames

        ## If a frame is a subframe, copy everything that is un-changed
        ## from the previous frame, and update the rest:
        for framenumber, frame in self.frames.items():
            if frame.KIND == 'subframe':
                prevframe = self.frames[str(frame.number-1)]
                subframe_ = copy.deepcopy(prevframe)
                allowed = frame.templates[frame.TEMPLATE].allowed
                for boxname in allowed:
                    if boxname not in frame.boxes.keys():
                        pass
                    elif ((boxname in frame.boxes.keys()) and
                    frame.boxes[boxname].content.startswith('ADD')):
                        subframe_.boxes[boxname].UpdateContent(
                            frame.boxes[boxname].content
                        )
                    else:
                        subframe_.boxes[boxname] = frame.boxes[boxname]

                frame.__dict__ = subframe_.__dict__.copy()
                frame.number += 1
            frame.InsertIntoTemplate()

    def CreateHTML(self):
        parsedir = os.path.join(self.inputdir, 'parse', '')
        if not os.path.isdir(parsedir):
            os.mkdir(parsedir)

        HTML = ''
        for framenumber, frame in self.frames.items():
            HTML += frame.HTML

        self.HTML = HTML

        with open(parsedir+'output.html', 'w') as pf:
            pf.write(self.HTML)

    def CreatePreview(self):
        ## Creating "screenshots" of the HTML preview pages using Selenium.

        windowsize   = (1706, 1040)
        scrolloffset = -80



        options = Options()
        options.headless = True
        options.add_argument("--no-sandbox");
        options.add_argument("--disable-extensions");
        options.add_argument("--dns-prefetch-disable");
        fmt = 'jpg'     # Default for screenshot quality is jpg.
        self.fmt = fmt

        url = 'file:///{}parse/output.html'.format(self.inputdir)
        driver = webdriver.Firefox(options=options, service_log_path=os.path.devnull)
        driver.set_window_size(windowsize[0], windowsize[1])
        driver.get(url)
        imgfiles = []
        scroll = windowsize[1]+scrolloffset
        for f in range(len(self.frames)):
            png = '{}parse/output_{:02d}.{}'.format(self.inputdir, f, fmt)
            imgfiles.append(png)
            driver.save_screenshot(png)
            driver.execute_script('window.scrollTo(0, '+str(scroll)+')')
            scroll += windowsize[1]+scrolloffset
            ## The following removes the alpha channels from the images,
            ## which is necessary for the pdf convert:
            command = 'convert '+png+' -background white -alpha remove -alpha off '+png
            call = subprocess.Popen([command], stdout=subprocess.PIPE, shell=True)
            (output, error) = call.communicate()
        driver.quit()

        self.imgfiles = list(np.sort(imgfiles))

    def CreatePDF(self):
        ## Convert images to PDF presentation, and delete preview.
        self.CreatePreview()

        outfile = '{}.pdf'.format(os.path.basename(os.path.normpath(self.inputdir)))
        with open(self.inputdir+outfile, 'wb') as f:
            f.write(img2pdf.convert(self.imgfiles))

        for imgfile in os.listdir(self.parsedir):
            if imgfile.endswith(self.fmt):
                os.remove('{}{}'.format(self.parsedir, imgfile))


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

        Frame.pagecount += (0 if self.KIND=='subframe' else 1)
        self.page = Frame.pagecount

    def ParseBackground(self):
        ## The frame background can be specified as a css statement with
        ## the BACKGROUND meta key word. A plain color or an image in the
        ## default image folder can also be specified with the shortcut
        ## keywords BACKGROUND_COLOR or BACKGROUND_IMG.
        rules = [
            ('BACKGROUND',       '{}'),
            ('BACKGROUND_COLOR', 'background-color: {}; '),
            ('BACKGROUND_IMG',   'background-image: url(../pictures/{}); '),
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
        rawboxes = re.findall(Box.regex_box, self.rawframe)
        boxes = {}
        for rawbox in rawboxes:
            box = Box(rawbox, self.templates[self.TEMPLATE])
            boxes[box.name] = box

        self.boxes = boxes

    def InsertIntoTemplate(self):

        HTML = self.templates[self.TEMPLATE].content
        ## Insert page number and background:
        HTML = HTML.replace('{page}', '{}'.format(self.page))
        HTML = HTML.replace('{background}', '{}'.format(self.background))

        ## Determine width of title (used in some templates):
        if 'BOXTITLE' in self.boxes.keys():
            titlewidth = self.fonts['bold'].getlength(
                # '{}'.format(self.boxes['BOXTITLE'].content)
                ' {} '.format(self.boxes['BOXTITLE'].content)
            )
            titlewidth += 2*int(self.styles['boxpadding'])
            self.boxes['BOXTITLE'].SetStyle(('width', '{}px'.format(titlewidth)))
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
                    box.SetStyle(eval(df[2]))

        for boxname, box in self.boxes.items():
            HTML = HTML.replace('{{{} style}}'.format(box.name), box.style)
            HTML = HTML.replace('{{{}}}'.format(box.name), box.content)

        self.HTML = HTML


class Box(object):

    regex_box = '(BOX\w*) *= *{\s*((style *= *"(.*)")\s*)*((.|\s)*?)\s*}'
    regex_li  = '\s*<li .*>((.|\s)*)<\/li>'

    def __init__(self, rawbox, template):
        self.name     = rawbox[0]
        self.style    = rawbox[2]
        self.content  = rawbox[4]
        self.template = template

        self.Appear()

    def SetStyle(self, *styles):
        ## Append new style commands to the existing style string:
        newstyle = self.style.lstrip('style="').rstrip('"')
        for key, value in styles:
            newstyle += ' {}: {};'.format(key, value)

        newstyle = 'style="{}"'.format(newstyle)
        self.style = newstyle

    def UpdateContent(self, newcontent, rev=False):

        if rev == True:
            first, second = newcontent, self.content.replace('ADD', '')
        else:
            first, second = self.content, newcontent.replace('ADD', '')

        lis = re.search(Box.regex_li, second)
        if lis and '</ul>' in first:
            third = first.replace('</ul>', '{}\n</ul>'.format(lis[0]))
        elif lis and '</ol>' in first:
            third = first.replace('</ol>', '{}\n</ol>'.format(lis[0]))
        else:
            third = first + second

        self.content = third

    def Appear(self):
        ## Boxes are hidden by default. This makes them visible.

        if self.style or self.content:
            self.SetStyle(('visibility', 'visible'))



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
    pres.CreatePreview()
if sys.argv[2] in ['--pdf', '--PDF']:
    pres.CreatePDF()
