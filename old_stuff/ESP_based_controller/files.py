
import sys
def savetofile(pointstosave): # the points to save should have format of [[light, pot],[light,pot]]
    import os
    if(os.listdir().count('data.py')):
        import data
        datapoints=[]
        del sys.modules["data"]
        import data
        try:
            datapoints=data.points
            datapoints.append(pointstosave)
        except:
            datapoints.append(pointstosave)
        del sys.modules["data"]
        #getting ready to reimporting data file
    else:
        datapoints=[]
        datapoints.append(pointstosave)
        print("new file")
    
    #writing files to the data.py  
    f=open("data.py","w")
    f.write("points="+str(datapoints)+"\r\n")
    f.close()


def cleardatafile(): # the points to save should have format of [[light, pot],[light,pot]]
    import os
    f=open("data.py","w")
    f.write("points=[]")
    f.close()
    
    
def replacefile(pointstosave):
    import os
    if(os.listdir().count('data.py')):
        f=open("data.py","w")
        f.write("points="+str(pointstosave)+"\r\n")
        f.close()
    else:
        return 0


    
def readfile():

    import os
    if(os.listdir().count('data.py')):
        import data
        if(data.points):
            return(data.points)
        else:
            print("returning blank")
            return([])
    else:
        return([])
    
        #also make this go home

def resetlog():
    import os
    try:
        os.remove("log.py")
    except:
        print("no log file to remove")
    
def resetprefs(mode):
    import os
    f=open("prefs.py","w")
    if(mode ==0):
        f.write("mode=0" + "\r\n")
    else:
        f.write("mode=1" + "\r\n")
    f.close()
    
    
def setprefs():
    import os
    f=open("prefs.py","w")
    f.write("log=True" + "\r\n")
    f.close()
    
def savetolog(*logtext): # the points to save should have format of [[light, pot],[light,pot]]
    import os
    if(os.listdir().count('log.py')):
        f=open("log.py","a")
        try:
            print("writing",logtext)
            f.write(str(logtext)+"\r\n")
        except:
            print("errr")
    else:
        f=open("log.py","w")
        f.write(str(logtext)+",")
    
    #writing files to the data.py  
    f.close()
