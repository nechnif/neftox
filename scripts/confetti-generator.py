#!/usr/bin/env python3

import numpy as np
import os, sys, argparse
import random
import datetime as dt

dir = dir_path = os.path.dirname(os.path.realpath(__file__))

if __name__ == '__main__':
   parser = argparse.ArgumentParser()
   parser.add_argument('--img',  type=str, nargs='?', const=1, default='./_confetti.html')
   parser.add_argument('--out',  type=str, nargs='?', const=1, default=dir+'/_confetti.html')
   parser.add_argument('--seed', type=int, nargs='?', const=1, default=int(dt.datetime.now().strftime('%H%M%S')))
   parser.add_argument('--num',  type=int, nargs='?', const=1, default=20)
   parser.add_argument('--size', type=int, nargs='?', const=1, default=5)
   parser.add_argument('--rot',  type=int, nargs='?', const=1, default=0)
   args = parser.parse_args()

   argsdict = {
    'img'  : args.img,
    'out'  : args.out,
    'seed' : args.seed,
    'num'  : args.num,
    'size' : args.size,
    'rot'  : args.rot,
    }
   # print(argsdict)


random.seed(argsdict['seed'])

## Create random positions within figure size:
top  = [random.randint(0, 100) for i in range(argsdict['num'])]
left = [random.randint(0, 100) for i in range(argsdict['num'])]
rot  = [random.randint(-180, 180) for i in range(argsdict['num'])]

fig = (
    '<div class="" style="position: absolute; width: 3000px; height: 3000px;">\n'
    '    <!-- created with scripts/confetti-generator.py -->\n'
    '{IMG}'
    '</div>\n'
)

img = '    <img src="{SRC}" style="position: absolute; top: {TOP}%; left: {LEFT}%; width: {SIZE}%; transform: rotate({ROT}deg);">\n'

for i in range(argsdict['num']):
    img_ = img.replace( '{SRC}',  argsdict['img'])
    img_ = img_.replace('{TOP}',  str(top[i]))
    img_ = img_.replace('{LEFT}', str(left[i]))
    img_ = img_.replace('{SIZE}', str(argsdict['size']))
    img_ = img_.replace('{ROT}',  str(rot[i]))
    fig = fig.replace(  '{IMG}',  img_+'{IMG}')

fig = fig.replace('{IMG}', '')

with open(argsdict['out'], 'w') as pf:
    pf.write(fig)

print()
print(fig)
print()
print('Seed used: ' + str(argsdict['seed']))
