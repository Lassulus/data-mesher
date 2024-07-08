# data-mesher

This daemon is used to exchange data in mesh based networks where every peer can
talk to another peer directly. It should securely exchange information signed by
the sender. There should be no central server and peers should be able to verify
independently the correctness of the data. The network should be self healing,
Outdated hosts will be removed after a configurable decay time.

Right now this is a very rough prototype and not usable. The first usecase will
be DNS inside a zerotier or mycelium based network.
