import kopf
import pykube
import yaml
import time
import logging
import kubernetes

max_memory = 64
max_cpu = 250
kubernetes.config.load_kube_config()
apicustom = kubernetes.client.CustomObjectsApi()
api = pykube.HTTPClient(pykube.KubeConfig.from_env())
namespace_limp = "limps-ns1"


def set_resource_controlled(name, namespace,kind):
    apicustom.patch_namespaced_custom_object(
        group="kopf.dev",
        version="v1",
        namespace=namespace,
        plural=kind,
        name= name,
        body={"status": {"phase":"Controlled"}}
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
    settings.peering.standalone = True
    #get namespace of this operator



@kopf.on.create('limitedpods')
def create_fn(spec,**kwargs):
  set_resource_controlled(spec.get('name', 'default-name'), namespace_limp, "limitedpods")

  pods = pykube.Pod.objects(api).filter(namespace=namespace_limp, selector={'child': 'limitedpods'})
  state = len(pods.response['items'])

  if state < 1:
      text_to_print = "I am the only one"
      memory = max_memory
      cpu = max_cpu
  else:
      text_to_print = "I am not alone"
      memory = max_memory//(state+1)
      cpu = max_cpu//(state+1)

  # Render the pod yaml with some spec fields used in the template.
  doc = yaml.safe_load(f"""
      apiVersion: v1
      kind: Pod
      metadata:
        name: {spec.get('name', 'default-name')}
        labels: 
          child: 'limitedpods'
        namespace: '{namespace_limp}'
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

  # Make it our child: assign the namespace, name, labels, owner references, etc.
  kopf.adopt(doc)

  # Actually create an object by requesting the Kubernetes API.
  pod = pykube.Pod(api, doc)
  pod.create()

  apicustom.patch_namespaced_custom_object(
        group="kopf.dev",
        version="v1",
        namespace=namespace_limp,
        plural="limitedpods",
        name= spec.get('name', 'default-name'),
        body={"status": {"message": f"We are {state+1} limps","memory": f"{memory}Mi", "cpu": f"{cpu}m", "phase":"Running"}}
      )


@kopf.timer('limitedpods', interval=15, initial_delay=10,field='status.phase', value='Running')
def timer_fn(spec,**kwargs):
  set_resource_controlled(spec.get('name', 'default-name'), namespace_limp, "limitedpods")

  logging.debug(spec)
  api = pykube.HTTPClient(pykube.KubeConfig.from_env())
  state = 0
  
  pods = pykube.Pod.objects(api).filter(namespace=namespace_limp, selector={'child': 'limitedpods'})
  state = len(pods.response['items'])

  if state <= 1:
      text_to_print = "I am the only one"
      memory = max_memory
      cpu = max_cpu
  else:
      text_to_print = "I am not alone"
      memory = max_memory//(state)
      cpu = max_cpu//(state)

  find_pod = False

  for pod in pods:
    name = pod.obj['metadata']['name']
    memory_assigned = pod.obj['spec']['containers'][0]['resources']['limits']['memory']
    logging.debug(name)
    if name == spec.get('name', 'default-name'):
       find_pod = True
    if name == spec.get('name', 'default-name') and memory_assigned != f"{memory}Mi" and pod.obj['status']['phase'] == 'Running':
      pod.delete()
      #Update the pod memory and cpu
      doc = yaml.safe_load(f"""
        apiVersion: v1
        kind: Pod
        metadata:
          name: {spec.get('name', 'default-name')}
          labels: 
            child: 'limitedpods'
          namespace: '{namespace_limp}'
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
      kopf.adopt(doc)
      pods = pykube.Pod.objects(api).filter(namespace=pykube.all, selector={'child': 'limitedpods'}, field_selector={'metadata.name': name})
      while len(pods) != 0:
          time.sleep(1)
          pods = pykube.Pod.objects(api).filter(namespace=pykube.all, selector={'child': 'limitedpods'}, field_selector={'metadata.name': name})
    
      pod = pykube.Pod(api, doc)
      pod.create()

      apicustom.patch_namespaced_custom_object(
        group="kopf.dev",
        version="v1",
        namespace=namespace_limp,
        plural="limitedpods",
        name= name,
        body={"status": {"message": f"We are {state} limps","memory": f"{memory}Mi", "cpu": f"{cpu}m", "phase":"Running"}}
      )
  # if not find_pod:
  #   create_fn(spec)
      
  set_resource_running(spec.get('name', 'default-name'), namespace_limp, "limitedpods")
