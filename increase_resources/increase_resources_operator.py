import kopf
import pykube
import yaml
import time
import logging
import kubernetes
import random

kubernetes.config.load_kube_config()
apicustom = kubernetes.client.CustomObjectsApi()
api = pykube.HTTPClient(pykube.KubeConfig.from_env())

def set_resource_controlled(name, namespace,kind):
    apicustom.patch_namespaced_custom_object(
        group="kopf.dev",
        version="v1",
        namespace=namespace,
        plural=kind,
        name= name,
        body={"status": {"phase":"Incremented"}}
    )

def set_resource_running(name, namespace,kind):
    apicustom.patch_namespaced_custom_object(
        group="kopf.dev",
        version="v1",
        namespace=namespace,
        plural=kind,
        name= name,
        body={"status": {"phase":"Running"}}
    )

@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.posting.level = logging.DEBUG
    # settings.peering.priority = 100


@kopf.timer('limitedpods', interval=30, initial_delay=20,field='status.phase',value = 'Running')
def timer_fn(spec,**kwargs):

    set_resource_controlled(spec.get('name', 'default-name'),spec.get("namespace","default") , "limitedpods")
    logging.debug(spec)
    
    state = 0
    
    pods = pykube.Pod.objects(api).filter(namespace=pykube.all, selector={'child': 'limitedpods'})
    state = len(pods.response['items'])

    if state <= 1:
        text_to_print = "I am the only one"
    else:
        text_to_print = "I am not alone"


    for pod in pods:
        name = pod.obj['metadata']['name']
        memory_assigned = pod.obj['spec']['containers'][0]['resources']['limits']['memory']
        cpu_assigned = pod.obj['spec']['containers'][0]['resources']['limits']['cpu']
        logging.debug(name)
        if name == spec.get('name', 'default-name') and random.random() > 0.2 and pod.obj['status']['phase'] == 'Running':
            memory = int(float(memory_assigned[:-2])*1.2) 
            cpu = int(float(cpu_assigned[:-1])*1.2)
            namespace = pod.obj['metadata']['namespace']
            pod.delete()
            #Update the pod memory and cpu
            doc = yaml.safe_load(f"""
                apiVersion: v1
                kind: Pod
                metadata:
                    name: {spec.get('name', 'default-name')}
                    labels: 
                      child: 'limitedpods'
                    namespace: {namespace}
                spec:
                    containers:
                    - name: the-only-one
                      image: busybox
                      command: ["sh", "-x", "-c"]
                      args:
                      - |
                        while true
                        do
                        echo "{text_to_print}, memory: {memory}Mi, cpu: {cpu}m"
                        sleep 10
                        done
                      resources:
                        limits:
                          memory: "{memory}Mi"
                          cpu: "{cpu}m"
            """)

            logging.info(f"updating {name}, {memory}Mi, {cpu}m")
            pods = pykube.Pod.objects(api).filter(namespace=pykube.all, selector={'child': 'limitedpods'}, field_selector={'metadata.name': name})
            while len(pods) != 0:
                time.sleep(1)
                pods = pykube.Pod.objects(api).filter(namespace=pykube.all, selector={'child': 'limitedpods'}, field_selector={'metadata.name': name})
            
            pod = pykube.Pod(api, doc)
            pod.create()
            
            apicustom.patch_namespaced_custom_object(
                group="kopf.dev",
                version="v1",
                namespace=namespace,
                plural="limitedpods",
                name= name,
                body={"status": {"message": f"We are {state} limps","memory": f"{memory}Mi", "cpu": f"{cpu}m","phase":"Running"}}
            )
            
    set_resource_running(spec.get('name', 'default-name'),spec.get("namespace","default") , "limitedpods")


