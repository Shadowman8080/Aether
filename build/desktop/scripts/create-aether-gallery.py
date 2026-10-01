#!/usr/bin/env python3
"""Generate Aether's original, resolution-independent wallpaper collection."""
from pathlib import Path
import json
import math
import random

assets = Path(__file__).resolve().parents[1] / 'assets/usr/share'
palettes = {
    'Twilight': ['#111b36', '#425cad', '#91bbec', '#c1a5e0'],
    'Ember': ['#2c1833', '#9d4264', '#ee936b', '#fbd4a0'],
    'Lagoon': ['#082d39', '#176471', '#5ab6b4', '#b8e6d0'],
    'Dune': ['#322a32', '#79616a', '#b99d88', '#ebd6b2'],
}
for style in range(6):
    for tone, colors in palettes.items():
        name = ['Ridgelines', 'Tidal', 'Orbit', 'Terraces', 'Prism', 'Nightfall'][style] + ' ' + tone
        ident = 'Aether' + name.replace(' ', '')
        folder = assets / 'wallpapers' / ident
        image = folder / 'contents/images/3840x2160.svg'
        image.parent.mkdir(parents=True, exist_ok=True)
        rng = random.Random(name)
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="3840" height="2160" viewBox="0 0 1920 1080"><defs><linearGradient id="sky" x2="0.8" y2="1"><stop stop-color="{colors[0]}"/><stop offset="1" stop-color="{colors[1]}"/></linearGradient></defs><rect width="1920" height="1080" fill="url(#sky)"/>']
        if style in (0, 1, 3):
            parts.append(f'<circle cx="1440" cy="270" r="115" fill="{colors[3]}" opacity=".7"/>')
            for layer in range(5):
                y = 400 + layer * 130
                if style == 0:
                    points = ' '.join(f'{x},{y+rng.randrange(-170, 120)}' for x in range(-100, 2100, 200))
                    shape = f'<polygon points="-100,1080 {points} 2100,1080"'
                elif style == 1:
                    shape = f'<path d="M-100,{y} C450,{y-400} 950,{y+420} 2020,{y-40} L2020,1080 L-100,1080Z"'
                else:
                    shape = f'<path d="M-50,{y} H{600+layer*80} Q{850+layer*80},{y} {850+layer*80},{y+160} H2020 V1080 H-50Z"'
                parts.append(shape + f' fill="{colors[(layer+2)%4]}" opacity=".85"/>')
        elif style == 2:
            for n in range(12):
                parts.append(f'<ellipse cx="1350" cy="730" rx="{180+n*85}" ry="{90+n*45}" transform="rotate(-28 1350 730)" fill="none" stroke="{colors[2+n%2]}" stroke-width="{4+n*2}" opacity="{.65-n*.035}"/>')
            parts.append(f'<circle cx="1350" cy="730" r="90" fill="{colors[3]}"/>')
        elif style == 4:
            for n in range(10):
                x = n*240-300
                parts.append(f'<path d="M{x},1080 L{x+600},60 L{x+1050},1080Z" fill="{colors[n%4]}" opacity=".48"/>')
        else:
            for n in range(160):
                parts.append(f'<circle cx="{rng.randrange(1920)}" cy="{rng.randrange(850)}" r="{rng.choice([1,1,2,3])}" fill="{colors[3]}" opacity="{rng.uniform(.2,.9):.2f}"/>')
            parts.append(f'<circle cx="1360" cy="280" r="95" fill="{colors[3]}"/><path d="M0,900 Q480,700 920,880 T1920,840 V1080 H0Z" fill="{colors[0]}"/>')
        image.write_text(''.join(parts) + '</svg>')
        (folder/'metadata.json').write_text(json.dumps({'KPlugin': {'Id': ident, 'Name': 'Aether · ' + name, 'License': 'CC0-1.0', 'Authors': [{'Name':'Aether Project'}]}}, indent=2))

names = ['Starfield', 'Aurora', 'Bubbles', 'Orbital', 'Tidal', 'Constellation', 'Rainfall', 'Horizon']
qml = '''// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
WallpaperItem {
    id: root
    readonly property int mode: MODE
    property real phase: 0
    Timer { interval: 50; repeat: true; running: root.visible && root.width > 0
        onTriggered: { root.phase += 0.025; art.requestPaint() } }
    Canvas {
        id: art; anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c=getContext("2d"), w=width, h=height, t=root.phase, m=root.mode;
            c.reset(); var g=c.createLinearGradient(0,0,w,h);
            g.addColorStop(0,"#0b1429"); g.addColorStop(1,"#26385d"); c.fillStyle=g; c.fillRect(0,0,w,h);
            var colors=["#80c9f1","#bca6e9","#7bddc3","#f0c5b0"];
            if(m===1 || m===4 || m===7) {
                for(var j=0;j<7;j++) {
                    c.beginPath(); c.moveTo(0,h);
                    for(var x=0;x<=w+16;x+=16) {
                        var y=h*(0.4+j*0.065)+Math.sin(x/w*6.28+t*(0.2+j*.04)+j)*h*(m===1?.19:.06);
                        c.lineTo(x,y);
                    }
                    c.lineTo(w,h);c.closePath();c.fillStyle=colors[j%4];c.globalAlpha=.12;c.fill();
                }
                if(m===7){c.globalAlpha=.6;c.fillStyle="#f0c5b0";c.beginPath();c.arc(w*.72,h*.32,Math.min(w,h)*.085,0,6.283);c.fill();}
            } else if(m===3) {
                for(var k=0;k<12;k++) {c.globalAlpha=.22;c.strokeStyle=colors[k%4];c.lineWidth=2;c.beginPath();
                    c.ellipse(w/2,h/2,w*(.08+k*.023),h*(.04+k*.026),t*.05+k*.13,0,6.283);c.stroke();}
            } else {
                for(var i=0;i<80;i++) {
                    var xx=((i*0.61803398875)%1)*w, yy=((i*0.41421356+t*(m===6?.025:.003))%1)*h;
                    c.fillStyle=colors[i%4];c.strokeStyle=colors[i%4];c.globalAlpha=.25+.3*(1+Math.sin(t+i))/2;
                    if(m===6){c.lineWidth=1;c.beginPath();c.moveTo(xx,yy);c.lineTo(xx-6,yy+24);c.stroke();}
                    else {var radius=m===2?12+(i%6)*7:1+(i%3);c.beginPath();c.arc(xx+Math.sin(t*.3+i)*8,yy,radius,0,6.283);if(m===2)c.stroke();else c.fill();}
                    if(m===5 && i%3===0){c.globalAlpha=.13;c.beginPath();c.moveTo(xx,yy);c.lineTo((xx+100)%w,(yy+65)%h);c.stroke();}
                }
            }
            c.globalAlpha=1;
        }
    }
}
'''
for mode, name in enumerate(names):
    ident = 'org.aether.saver.' + name.lower()
    folder = assets/'plasma/wallpapers'/ident
    (folder/'contents/ui').mkdir(parents=True, exist_ok=True)
    (folder/'contents/ui/main.qml').write_text(qml.replace('MODE', str(mode)))
    (folder/'metadata.json').write_text(json.dumps({'KPackageStructure':'Plasma/Wallpaper','KPlugin':{'Id':ident,'Name':'Aether '+name,'Description':'Animated background for the desktop or secure lock screen','License':'GPL-2.0-or-later','Authors':[{'Name':'Aether Project'}]}},indent=2))
print('Generated 24 wallpapers and 8 animated wallpaper/lock-screen plugins')
