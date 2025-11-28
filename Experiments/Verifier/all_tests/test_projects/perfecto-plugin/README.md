<i>**Important: As of May 24, 2024, the Perfecto Jenkins plugin will be deprecated. Current plugin installation will continue to work, but going forward, Perfecto will no longer provide bug fixes and maintenance services for this plugin. As an alternative, you can create a Jenkins pipeline with Perfecto Connect. To learn more, see [Jenkins plugin](https://help.perfecto.io/perfecto-help/content/perfecto/integrations/jenkins_plugin.htm#) > Step-by-step instructions > 4 | Work with Advanced usage scenarios > Create a Perfecto Connect pipeline.** </br></i>


<img src="https://github.com/PerfectoMobileSA/perfecto-plugin/blob/master/DOC/perfecto.jpg" height="75" width="300"/>

# Perfecto Jenkins Plugin

Perfecto Jenkins Plugin provides the ability to auto-create/ re-use existing Perfecto Connect tunnel-id in build environment. 


# Table of Contents

- [Perfecto Jenkins Plugin](#perfecto-jenkins-plugin)
- [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [1. Steps to Enable the plugin](#1-steps-to-enable-the-plugin)
    - [Screenshots](#screenshots)
      - [Mac](#mac)
      - [Windows](#windows)
    - [Advanced Options](#advanced-options)
  - [2. Usage](#2-usage)
    - [Maven Sample](#maven-sample)
    - [Gradle Sample](#gradle-sample)
  - [3. Steps to Stop Perfecto Connect](#3-steps-to-stop-perfecto-connect)
  - [Advanced Usage](#advanced-usage)
    - [Perfecto Connect Pipeline Sample](#perfecto-connect-pipeline-sample)
    - [Upload app to perfecto](#upload-app-to-perfecto)

## Prerequisites

* Download Perfecto Connect client, extract to any folder.
* Generate Perfecto Security Token (if not generated already) 
* Mac users should install Jenkins via [brew.](https://www.jenkins.io/download/lts/macos/)
* In Jenkins, navigate to Manage Jenkins > Manage Plugins view, available to administrators of a Jenkins environment. Search for “perfecto” under the Available tab, click on the checkbox near to it and then click on Install without restart button.

## 1. Steps to Enable the plugin 

1.	Click New Item in Jenkins home page.</br>
2.	Enter Your preferred Item name.</br>
3.	Select any project type except pipeline.</br>
4.	Click OK.</br>
5.	Select Perfecto Connect checkbox under Build Environment (Refer Screenshots section)</br>
6.	Note: Get help from your Jenkins Administrator to create the below Perfecto credentials:</br>
	a.	Select Add option next to Credentials dropdown and select Jenkins. </br>
	b.	Select option: “Perfecto” under Kind dropdown in Add Credentials window.</br>
	c.	Provide Your Cloud Name, Username and Security Token and click on Add.</br>
	
<img src="https://github.com/PerfectoMobileSA/perfecto-plugin/blob/master/DOC/cred.png" height="auto" alt="image"/></br>

7.	Provide Perfecto Connect Path in Perfecto Connect Path text field. </br>
	a.	E.g.: - /Users/Mymac/Downloads</br>
8.	Provide Perfecto Connect File Name in Perfecto Connect File Name text field.</br>
	a.	E.g.: - Mac – perfectoconnect</br>
	b.	E.g.: - Windows – perfectoconnect64.exe or perfectoconnect32.exe</br>

### Screenshots
#### Mac
<img src="https://github.com/PerfectoMobileSA/perfecto-plugin/blob/master/DOC/mac.png" height="auto" alt="image"/>
	 
#### Windows
<img src="https://github.com/PerfectoMobileSA/perfecto-plugin/blob/master/DOC/win.png" height="auto" alt="image"/>

### Advanced Options

You can provide Advanced options such as Perfecto Connect Additional Parameters, Override Tunnel ID  Name and Existing Tunnel ID.</br>
1.	Additional Parameters</br>
	a.	Provide Perfecto Connect parameters such as bridgeproxyip, bridgeproxyport</br>
	b.	E.g.: - --bridgeproxyip=127.0.0.1 --bridgeproxyport=8888</br>
2.	You can override Tunnel ID Environment Variable name in Override Tunnel ID Name in text field. (The default Jenkins Build Environment variable name is tunnelId)</br>
3.	You can reuse already created Tunnel ID in Existing Tunnel ID text field.</br>

<img src="https://github.com/PerfectoMobileSA/perfecto-plugin/blob/master/DOC/4.png" height="auto" alt="image"/></br>

## 2. Usage

### Maven Sample

<img src="https://github.com/PerfectoMobileSA/perfecto-plugin/blob/master/DOC/6.png" height="auto" alt="image"/>
 
### Gradle Sample

<img src="https://github.com/PerfectoMobileSA/perfecto-plugin/blob/master/DOC/7.png" height="auto" alt="image"/>
 
 
## 3. Steps to Stop Perfecto Connect

1.	Add a Post Build task under Post Build Action.</br>
2.	Enter the below script under Script text field.</br>

<img src="https://github.com/PerfectoMobileSA/perfecto-plugin/blob/master/DOC/5.png" height="auto" alt="image"/></br>
 
## Advanced Usage

### Perfecto Connect Pipeline Sample

1.	Create a new Pipeline and add the below code to pipeline script text field.</br>
2.	Update cloudName, securityToken and perfectoConnectPath as applicable.</br>

```import javax.swing.GroupLayout.ParallelGroup
import groovy.json.JsonSlurperClassic
import groovy.json.JsonSlurper
 
node {
String cloudName = "<<CLOUD NAME e.g. demo>>";
String securityToken = "<<SECURITY TOKEN>>";
String perfectoConnectPath = "/Users/myMac/Downloads/perfectoconnect";
    environment {
        tunnelId = ""
    }
    stage('perfectoconnect start'){
        if(cloudName.contains("<<")){
             error "Kindly update cloudName, securityToken and perfectoConnectPath"
        }
        String script = perfectoConnectPath + " start  -c " + cloudName + ".perfectomobile.com  -s " + securityToken;
        echo script;
        tunnelId = sh (script: script , returnStdout: true).trim()
        env.tunnelId = "${tunnelId}"
    }
    stage('script'){
        echo "Tunnel id: ${tunnelId}"
    }
    stage('perfectoconnect stop'){
        sh label: '', returnStdout: true, script: perfectoConnectPath + " stop"
    }
}
```

### Upload app to perfecto
	
Follow [this](https://developers.perfectomobile.com/display/TT/Upload+a+file+to+the+repository+via+API+using+Postman+or+cURL) documentation to use curl and upload app to perfecto media repository.
