
import kubernetes
import pykube

kubernetes.config.load_kube_config()
apicustom = kubernetes.client.CustomObjectsApi()
api = pykube.HTTPClient(pykube.KubeConfig.from_env())
apicore = kubernetes.client.CoreV1Api()


limps = apicustom.list_cluster_custom_object(group="kopf.dev", version="v1", plural="limitedpods")

#prin limps names

for limp in limps['items']:
    print(limp['metadata']['name'])
    print(limp['metadata']['namespace'])
    print(limp['status']['phase'])
    print(limp['status']['message'])
    print(limp['status']['memory'])
    print(limp['status']['cpu'])
