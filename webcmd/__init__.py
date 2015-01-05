# -*- coding: utf-8 -*-
"""
Created on Mon Dec 29 11:43:24 2014

@author: pablo
"""
from Queue import Queue
from flask import Flask, Response, jsonify, request, stream_with_context
import time, os
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

app = Flask(__name__)
subscriptions = []


def srender_template(template_name, **context):
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.render(context)
    return rv


# SSE "protocol" is described here: http://mzl.la/UPFyxY
class ServerSentEvent(object):

    def __init__(self, data):
        self.data = data
        self.event = None
        self.id = None
        self.desc_map = {
            self.data : "data",
            self.event : "event",
            self.id : "id"
        }

    def encode(self):
        if not self.data:
            return ""
        lines = ["%s: %s" % (v, k) 
                 for k, v in self.desc_map.items() if k]
        
        return "%s\n\n" % "\n".join(lines)


def notify():
    msg = str(time.time())
    for sub in subscriptions[:]:
        sub.put(msg)

class FileCmdGetter:
    filename = ''
    cmds = []
    
    
    def __init__(self, filename):
        self.filename = filename
    
    
    def read_cmds(self):
        self.cmds = []
        with open(self.filename, 'r') as cmdsfile:
            for line in cmdsfile:
                self.cmds.append(line.strip())
                
    def read_cmds_and_delete(self):
        self.read_cmds()
        os.unlink(self.filename)
        with open(self.filename, 'w') as cmdsfile:
            cmdsfile.write('')
                
    def get_cmds(self):
        return self.cmds
        

@app.route('/getcmds')
def getcmds():
    cmd_getter = FileCmdGetter('/tmp/cmds.txt')
    cmd_getter.read_cmds_and_delete()
    return jsonify(cmds=cmd_getter.get_cmds())


@app.route('/listcmds')
def listcmds():
    cmd_getter = FileCmdGetter('/tmp/cmds.txt')
    cmd_getter.read_cmds()
    return jsonify(cmds=cmd_getter.get_cmds())


@app.route('/getresponses')
def getresponses():
    debug_template = """
    <html>
       <head>
            <script src="http://code.jquery.com/jquery-latest.js"></script>
            <script>                
                function update() {
                    $.get('/webcmd/update', function( data ) {
                        if (!jQuery.isEmptyObject(data)) {
                            console.log(data);
                            var innerDiv = document.createElement('div');
                            innerDiv.innerHTML = data;
                            eventOutputContainer.appendChild(innerDiv)
                        }
                    });
                }
            </script>
       </head>
       <body>
        <h1>Server sent events %s</h1>
        <div id="event"></div>
        <script>
            $( document ).ready(function() {
                eventOutputContainer = document.getElementById("event");
                setInterval(function() {
                    update();
                }, 10000);
            });
        </script>
         <!--script type="text/javascript">

         var eventOutputContainer = document.getElementById("event");
         var evtSrc = new EventSource("/subscribe");

         evtSrc.onmessage = function(e) {
             console.log(e.data);
             var innerDiv = document.createElement('div');
             innerDiv.innerHTML = e.data;
             eventOutputContainer.appendChild(innerDiv)
         };

         </script-->
       </body>
     </html>
    """ % (time.strftime("%H:%M:%S"))
    return(debug_template)


@app.route("/update")
def update():
    cmd_getter = FileCmdGetter('/tmp/resps.txt')
    cmd_getter.read_cmds_and_delete()
    temp = srender_template('table.html', lines=cmd_getter.get_cmds())
    #print("temp="+temp)
    return temp

@app.route("/subscribe")
def subscribe():
    def gen():
        q = Queue()
        subscriptions.append(q)
        try:
            while True:
                result = q.get()
                cmd_getter = FileCmdGetter('/tmp/resps.txt')
                cmd_getter.read_cmds_and_delete()
                temp = srender_template('table.html', lines=cmd_getter.get_cmds())
                ev = ServerSentEvent(temp.strip().replace('\n',''))
                encoded = ev.encode()
                for line in str(encoded).splitlines():
                    yield line
                yield '\n\n'
        except GeneratorExit: # Or maybe use flask signals
            subscriptions.remove(q)
    return Response(gen(), mimetype="text/event-stream")


@app.route('/listresponses')
def listresponses():
    cmd_getter = FileCmdGetter('/tmp/resps.txt')
    cmd_getter.read_cmds()
    return jsonify(cmds=cmd_getter.get_cmds())
    

@app.route('/putresponse', methods=['POST'])
def putresponse():
    with open('/tmp/resps.txt', 'a') as respfile:
        respfile.write(request.form['text'])
    notify()
    return "ok"
   

@app.route('/addcmd')
def addcmds():
    cmd = request.args.get('cmd')
    with open('/tmp/cmds.txt', 'a') as cmdsfile:
        cmdsfile.write(cmd + '\n')
    return "ok"


if __name__ == '__main__':
    app.debug = True
    app.run(threaded=True)
