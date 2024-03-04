import kopf
import pykube
import yaml
import time
import logging
import kubernetes
import random
import numpy as np
import os

kubernetes.config.load_kube_config()
apicustom = kubernetes.client.CustomObjectsApi()
api = pykube.HTTPClient(pykube.KubeConfig.from_env())
apicore = kubernetes.client.CoreV1Api()
namespaces_limps = ["limps-ns1","limps-ns2"]

path = os.path.join(os.path.dirname(__file__), '../limited_pods/cr.yaml')
tmpl = open(path, 'rt').read()

def set_resource_controlled(name, namespace,kind):
    apicustom.patch_namespaced_custom_object(
        group="kopf.dev",
        version="v1",
        namespace=namespace,
        plural=kind,
        name= name,
        body={"status": {"phase":"Moving"}}
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
    #create namespaces
    for ns in namespaces_limps:
        try:
            namespace = kubernetes.client.V1Namespace()
            namespace.metadata = kubernetes.client.V1ObjectMeta(name=ns)
            apicore.create_namespace(namespace)
        except:
            pass

    #get namespaces list
    namespaces = apicore.list_namespace()

    for ns in namespaces.items:
        logging.debug(ns.metadata.name)


@kopf.timer('limitedpods', interval=35, initial_delay=20,field='status.phase',value = 'Running')
def timer_fn(spec,**kwargs):
    controlled_resource_namespace = spec.get("namespace","default")
    controlled_resource_name = spec.get('name', 'default-name')
    set_resource_controlled(controlled_resource_name,controlled_resource_namespace , "limitedpods")
    logging.debug(spec)
    state = {ns : 0 for ns in namespaces_limps}

    limps = apicustom.list_cluster_custom_object(group="kopf.dev", version="v1", plural="limitedpods")

    #filter pods based on namespace
    for limp in limps['items']:
        state[limp['metadata']['namespace']] += 1

    logging.debug("State: "+ str(state))
    n_namespaces = len(namespaces_limps)
    number_of_limps = sum(state.values())

    desired_ns_limps = number_of_limps/n_namespaces

    #calculate probability of moving the limp
    p_move = 1 - desired_ns_limps/state[controlled_resource_namespace]

    ns_to_move = controlled_resource_namespace
    if random.random() < p_move:
        n_limps_here =  state.pop(controlled_resource_namespace)

        moving_to_exp = np.exp([(desired_ns_limps-n_limps_ns) for n_limps_ns in state.values()])
        probs_moving_to = moving_to_exp/np.sum(moving_to_exp, axis = 0)

        ns_to_move = np.random.choice(list(state.keys()), p = probs_moving_to)
        
        logging.debug(f"Moving {controlled_resource_name} from {controlled_resource_namespace} to {ns_to_move}")

        #delete the custom resource from the current namespace
        apicustom.delete_namespaced_custom_object(
            group="kopf.dev",
            version="v1",
            namespace=controlled_resource_namespace,
            plural="limitedpods",
            name= controlled_resource_name,
            body=kubernetes.client.V1DeleteOptions()
        )
        #create the custom resource in the new namespace
        text = tmpl.format(name=controlled_resource_name,namespace = ns_to_move)
        limitpod = yaml.safe_load(text)
        apicustom.create_namespaced_custom_object(
            group="kopf.dev",
            version="v1",
            namespace=ns_to_move,
            plural="limitedpods",
            body=limitpod
        )
    else:
        set_resource_running(controlled_resource_name,controlled_resource_namespace , "limitedpods")


