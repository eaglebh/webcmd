# -*- coding: utf-8 -*-
"""
Created on Mon Dec 29 11:43:24 2014

@author: pablo
"""
from Queue import Queue
from flask import Flask, Response, jsonify, request, json, url_for
from werkzeug import secure_filename
import time, os
import pyte
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

UPLOAD_FOLDER = '/var/www/webcmd/webcmd/static/upload'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
subscriptions = []

screen = pyte.Screen(175, 45)
stream = pyte.Stream()
stream.attach(screen)

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
    resp = jsonify(cmds=cmd_getter.get_cmds())
    return resp


@app.route('/getweb2srv')
def getweb2srv():
    up_getter = FileCmdGetter('/tmp/ups.txt')
    up_getter.read_cmds_and_delete()
    resp = jsonify(web2srv=up_getter.get_cmds())
    return resp


@app.route('/getsrv2web')
def getsrv2web():
    down_getter = FileCmdGetter('/tmp/downs.txt')
    down_getter.read_cmds_and_delete()
    resp = jsonify(srv2web=down_getter.get_cmds())
    return resp
    

@app.route('/listcmds')
def listcmds():
    cmd_getter = FileCmdGetter('/tmp/cmds.txt')
    cmd_getter.read_cmds()
    resp = jsonify(cmds=cmd_getter.get_cmds())
    return resp.get_data().decode('string_escape')


@app.route('/getresponses')
def getresponses():
    debug_template = """
    <html>
       <head>
            <script src="http://code.jquery.com/jquery-latest.js"></script>
            <script>                
                function update() {
                    $.get('""" + url_for('updateRemove') + """', function( data ) {
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
        <h1>Server sent events </h1>
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
    """
    return(debug_template)


@app.route("/updateRemove")
def updateRemove():
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
                #result = q.get()
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
    

@app.route('/showscreen')
def showscreen():
    str_screen = ''
    for idx, line in enumerate(screen.display, 1):
        str_screen += "{0:2d} {1}{2}".format(idx, line, '<br>')
    return str_screen


@app.route('/putresponse', methods=['POST'])
def putresponse():
    text = request.form['text']
    stream.feed(text)
    with open('/tmp/resps.txt', 'a') as respfile:
        respfile.write(text)
    notify()
    return "ok"
   

@app.route('/addcmd')
def addcmds():
    cmd = request.args.get('cmd')
    with open('/tmp/cmds.txt', 'a') as cmdsfile:
        cmdsfile.write(cmd + '\n')
    return "ok"


@app.route('/addup')
def addups():
    up = request.args.get('up')
    with open('/tmp/ups.txt', 'a') as upsfile:
        upsfile.write(up + '\n')
    return "ok"


@app.route('/adddown')
def adddowns():
    down = request.args.get('down')
    with open('/tmp/downs.txt', 'a') as downsfile:
        downsfile.write(down + '\n')
    return "ok"


@app.route('/upload/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        myfile = request.files['file']        
        if myfile:            
            filename = secure_filename(myfile.filename)
            print("filename="+str(os.path.join(app.config['UPLOAD_FOLDER'], filename)))
            myfile.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return "ok"
    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload File</h1>
    <form action="" method=post enctype=multipart/form-data>
      <p><input type=file name=file>
         <input type=submit value=Upload>
    </form>
    '''
    

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', threaded=True)
