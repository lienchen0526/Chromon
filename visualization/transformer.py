import json
import os
from typing import Any, Dict, TypedDict, Union, Optional, List, Tuple
from dataclasses import dataclass

IN_FILE = os.path.join(os.path.split(os.getcwd())[0], "logs", "lien-complete-facebook.04.27-1123.log")
OUT_DIR = os.path.join(".", "output", "tst.json")
Node = TypedDict(
    "Node",
    {
        "properties": Dict[str, Any],
        "_node_type": str,
        "_node_class": str,
        "_display": str,
        "_color": str,
        "id": Union[str, int]
    }
)

Edge = TypedDict(
    "Edge",
    {
        "id": Union[str, int],
        "type": str,
        "properties": Dict[str, Any],
        "source": Union[str, int],
        "target": Union[str, int],
        "_display": str,
        "eid": Optional[int]
    }
)

assert os.path.exists(IN_FILE)

nodeSet = set()
nodes: List[TypedDict("node", {"data": Node})] = []
edges: List[TypedDict("edge", {"data": Edge})] = []

def frameCreated(timestamp: str, event_name: str, eventData: dict) -> None:
    # [Main Frame Created]
    # [Sub-Frame Created]
    frameUID = eventData.get("frameUID")
    assert type(frameUID) == str, f"eventData: {eventData}, newFrameUID: {frameUID}"

    data = eventData.get("frameInfo")
    node = {
        "id": frameUID,
        "properties": data,
        "_display": data.get("title") if data.get("title") else data.get("url", {}).get("netloc"),
        "_node_type": "Main-Frame" if data.get("mainFrame") else "Sub-Frame",
        "_node_class": "Frame",
        "_color": "#1F77B4" if data.get("mainFrame") else "#AEC7E8"
    }
    if not frameUID in nodeSet:
        nodeSet.add(frameUID)
        nodes.append({"data": node})
    
    if data.get("parentFrameUID"):
        edge = {
            "id": max((x.get("data").get("id") for x in edges)) + 1,
            "type": event_name,
            "properties": {"timestamp": timestamp},
            "source": data.get("parentFrameUID"),
            "target": frameUID,
            "_display": event_name
        }
        edges.append({"data": edge})
    return None
 
def frameExecuteScript(timestamp: str, event_name: str, eventData: dict) -> None:
    # [Frame Execute Script]
    script = eventData.get("Script")
    node = {
        "id": script.get("domainHash"),
        "_node_type": "JavaScript",
        "_node_class": "Script",
        "_display": script.get("domain"),
        "_color": "#FFBB78",
        "properties": script
    }
    if node.get("id") not in nodeSet:
        nodeSet.add(node.get("id"))
        nodes.append({"data": node})
    
    edge = {
        "id":  max((x.get("data").get("id") for x in edges), default = 0) + 1,
        "type": event_name,
        "properties": {"timestamp": timestamp},
        "source": eventData.get('frameUID'),
        "target": node.get("id"),
        "_display": event_name
    }
    edges.append({"data": edge})
    return None

def frameNavigated(timestamp: str, event_name: str, eventData:dict) -> None:
    # [Frame Navigate by User]
    # [Frame Navigate by Script]
    # [Frame Navigate by Other]
    # [Frame Navigate by HTML]
    # [Frame Navigate by HTTP]

    newFrameId = eventData.get('frameUID')
    if type(newFrameId) != str:
        print(f"Invalid: {eventData}")
    data = eventData.get('frameInfo')
    title = data.get("title").encode('utf-8').decode() if data.get("title") else None
    node = {
        "id": newFrameId,
        "properties": data,
        "_display": title if title else data.get("url", {}).get("netloc"),
        "_node_type": "Main-Frame" if data.get("mainFrame") else "Sub-Frame",
        "_node_class": "Frame",
        "_color": "#1F77B4" if data.get("mainFrame") else "#AEC7E8"
    }
    nodes.append({"data": node})
    edge = {
        "id": max((x.get("data").get("id") for x in edges)) + 1,
        "type": event_name,
        "properties": {"timestamp": timestamp},
        "source": eventData.get("originFrameUID"),
        "target": newFrameId,
        "_display": event_name
    }
    edges.append({"data": edge})
    pass

def frameAttachToFrame(timestamp: str, event_name: str, eventData: dict) -> None:
    # [Frame Attach to Frame]
    frameUID = eventData.get('frameUID')
    data = eventData.get('frameInfo')
    title = data.get("title").encode('utf-8').decode() if data.get("title") else None
    node = {
        "id": frameUID,
        "properties": data,
        "_display": title if title else data.get("url") if data.get("url") else "Empty",
        "_node_type": "Main-Frame" if data.get("mainFrame") else "Sub-Frame",
        "_node_class": "Frame",
        "_color": "#1F77B4" if data.get("mainFrame") else "#AEC7E8"
    }
    nodes.append({"data": node})
    edge = {
        "id": max((x.get("data").get("id") for x in edges)) + 1,
        "type": event_name,
        "properties": {"timestamp": timestamp},
        "source": frameUID,
        "target": eventData.get('parentFrameUID'),
        "_display": event_name
    }
    edges.append({"data": edge})
    pass

def scriptCreateSubFrame(timestamp: str, event_name: str, eventData: dict) -> None:
    # [Script Create Sub-Frame]
    scriptId = eventData.get('scriptDomainHash')
    frameUID = eventData.get('frameUID')
    if isinstance(scriptId, dict):
        node = {
            "id": scriptId.get("url") if scriptId.get("url") else scriptId.get("scriptId"),
            "properties": scriptId,
            "_display": scriptId.get('scriptId'),
            "_node_type": "JavaScript",
            "_node_class": "Script",
            "_color": "#FFBB78"
        }
        if not node.get("id") in nodeSet:
            nodeSet.add(node.get("id"))
            nodes.append({"data": node})
        scriptId = node.get("id")
    edge = {
        "id": max((x.get("data").get("id") for x in edges)) + 1,
        "type": event_name,
        "properties": {"timestamp": timestamp},
        "source": scriptId,
        "target": frameUID,
        "_display": event_name
    }
    edges.append({"data": edge})
    return None

def scriptInitiateRemoteScript(timestamp: str, event_name: str, eventData: dict) -> None:
    # [Script Initiate Remote Script]
    parentScript = eventData.get("parentScript")
    childScript = eventData.get("childScript")
    if parentScript.get('domainHash') == "Null/Null":
        if "Null/Null" not in nodeSet:
            node = {
                "id": "Null/Null",
                "properties": parentScript,
                "_display": parentScript.get('scriptId'),
                "_node_type": "JavaScript",
                "_node_class": "Script",
                "_color": "#FFBB78"
            }
            nodes.append({"data": node})
            nodeSet.add(node.get("id"))
    if not childScript.get("domainHash") in nodeSet:
        node = {
            "id": childScript.get("domainHash"),
            "properties": childScript,
            "_display": childScript.get("domain"),
            "_node_type": "JavaScript",
            "_node_class": "Script",
            "_color": "#FFBB78"
        }
        nodes.append({"data": node})
        nodeSet.add(node.get("id"))
    edge = {
        "id": max((x.get("data").get("id") for x in edges)) + 1,
        "type": event_name,
        "properties": {"timestamp": timestamp},
        "source": parentScript.get('domainHash'),
        "target": childScript.get("domainHash"),
        "_display": event_name
    }
    edges.append({"data": edge})
    pass

def frameInfoUpdate(timestamp: str, event_name: str, eventData: dict) -> None:
    # [Frame Info Update to]
    newFrameUID = eventData.get("frameNewUID")
    assert type(newFrameUID) == str, f"eventData: {eventData}, newFrameUID: {newFrameUID}"
    data = eventData.get("frameInfo")
    title = data.get("title").encode('utf-8').decode() if data.get("title") else None
    node = {
        "id": newFrameUID,
        "properties": data,
        "_display": title if title else data.get("url", {}).get("netloc", "Empty"),
        "_node_type": "Main-Frame" if data.get("mainFrame") else "Sub-Frame",
        "_node_class": "Frame",
        "_color": "#1F77B4" if data.get("mainFrame") else "#AEC7E8"
    }
    nodes.append({"data": node})
    edge = {
        "id": max((x.get("data").get("id") for x in edges)) + 1,
        "type": event_name,
        "properties": {"timestamp": timestamp},
        "source": eventData.get('frameOriginUID'),
        "target": newFrameUID,
        "_display": event_name
    }
    edges.append({"data": edge})
    pass

def main():
    mapping = {
        "[Frame Execute Script]": frameExecuteScript,
        "[Frame Navigate by User]": frameNavigated,
        "[Frame Navigate by Script]": frameNavigated,
        "[Frame Navigate by Other]": frameNavigated,
        "[Frame Navigate by HTTP]": frameNavigated,
        "[Frame Navigate by HTML]": frameNavigated,
        "[Main Frame Created]": frameCreated,
        "[Sub-Frame Created]": frameCreated,
        "[Frame Attach to Frame]": frameAttachToFrame,
        "[Script Create Sub-Frame]": scriptCreateSubFrame,
        "[Script Initiate Remote Script]": scriptInitiateRemoteScript,
        "[Frame Info Update to]": frameInfoUpdate
    }
    with open(IN_FILE) as fd:
        for line in fd:
            try:
                line = line.split(' - ')
                line = " - ".join([line[-2], line[-1]])
                info = json.loads(line)
                print("success")
            except:
                continue
            event: str = info.get("event", "")
            eid, event_name = event.split(" - ")
            event_data = info.get("eventData")
            timestamp = info.get("timestamp")
            handler = mapping.get(event_name)
            if handler:
                handler(timestamp, event_name, event_data)
        pass

    graph = {
        "directed": True,
        "multigraph": True,
        "nodes": nodes,
        "edges": edges
    }
    with open(OUT_DIR, mode = 'w') as fd:
        json.dump(graph, fd)

if __name__ == "__main__":
    main()