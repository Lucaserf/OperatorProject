import kubernetes as k8s
import time 

k8s.config.load_kube_config()
namespaces = ["limps-ns1", "limps-ns2", "limps-ns3"]
api = k8s.client.CustomObjectsApi()


#get limps for each namespace and print them
while True:
    print("Observing limps")
    for ns in namespaces:
        print()
        print(f"\tNamespace: {ns}")
        limps = api.list_namespaced_custom_object(group="kopf.dev", version="v1",namespace=ns, plural="limitedpods")
        for limp in limps['items']:
            try:
                print(f"\t\tlimp name: {limp['metadata']['name']}",)
                print(f"\t\tlimp phase: {limp['status']['phase']}")
                print(f"\t\tlimp message: {limp['status']['message']}")
                print(f"\t\tlimp memory: {limp['status']['memory']}")
                print(f"\t\tlimp cpu: {limp['status']['cpu']}")
                print()
            except:
                pass
    time.sleep(5)