import os
import yaml
import time
import kubernetes

n_limpods = 16
names = [f'limpod-{i}' for i in range(n_limpods)]
namespace = "limps-ns1"
kubernetes.config.load_kube_config()
api = kubernetes.client.CustomObjectsApi()

for name in names:
    path = os.path.join(os.path.dirname(__file__), 'limited_pods/cr.yaml')
    tmpl = open(path, 'rt').read()
    text = tmpl.format(name=name,namespace = namespace)
    limitpod = yaml.safe_load(text)

    api.create_namespaced_custom_object(group="kopf.dev", version="v1", namespace=namespace, plural="limitedpods", body=limitpod)

    time.sleep(5)
