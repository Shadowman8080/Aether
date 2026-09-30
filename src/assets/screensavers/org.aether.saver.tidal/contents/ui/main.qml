// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
WallpaperItem {
    id: root
    readonly property int mode: 4
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
                    var rot=t*.05+k*.13, rx=w*(.08+k*.023), ry=h*(.04+k*.026);
                    for(var a=0;a<=64;a++){var ang=a*6.283185/64, px=Math.cos(ang)*rx, py=Math.sin(ang)*ry;var ex=w/2+px*Math.cos(rot)-py*Math.sin(rot),ey=h/2+px*Math.sin(rot)+py*Math.cos(rot);if(a===0)c.moveTo(ex,ey);else c.lineTo(ex,ey);}c.closePath();c.stroke();}
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
