# Programming a bitcoin-node in the p2p network

Understand how a bitcoin node, discovered others nodes in the network.

This is part of the learning series made by [Libreria Satoshi](https://libreriadesatoshi.com/), this is educational content, fair use.

## Pre-requeriment

Read the chapter 10, of the [bitcoin network book](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch10_network.adoc)

### Python Setup
This tool queries the hardcoded DNS seeds from the Bitcoin Core source code (`chainparams.cpp`) to discover the IP addresses of active Bitcoin nodes on the network.

#### Prerequisites

This project uses [uv](https://github.com/astral-sh/uv), an extremely fast Python package and project manager written in Rust.

##### 1. Install `uv`

If you don't have `uv` installed yet, run one of the following commands based on your operating system:

**macOS and Linux:**
```bash
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
```


## Module 1 - Intro and Peer Discovery

### Topics 
1. Explain how a node connect to the network, with no prior knowledge of address participants.
2. Obtain a list of IP of candidates nodes from seed DNS servers
3. Understand why you can fully trust the data from DNS servers

### Demo

1. Create a program querying dns seeds and list the address

## Module 2 - Addrman 

### Topics 
1. Explain once a BTC node bootstrap for the 1st time collect all the other peers in the network
2. What data structures are used to hold the list of available peers

### Demo

1. Store all the address of availables peers in the network, using the trustworthy DNS seeds hardcoded from BTC Core.


## Module 3- [Message Structure](https://learnmeabitcoin.com/technical/general/compact-size/)

### Topics 
1. Message Structure - Verack/Version

### Demo

1. Define Verack/Version payload. The handshake Bitcoin core use to send/receive message from others peers


## Module 4 - Connect to a peer

### Topics 
1. What is a Socket?
2. TCP Socket
3. TCP Handshake
4. Bitcode P2P hanshake via Verack/Version message exchange

### Demo

1. Use TCP to connect with others peers via Verack/Version with others Bitcoin nodes

## Module 5 - Incoming connections and addr relay

### Topics 
1. Receive/Send peer message connections

### Demo

1. Create a server to show message exchange on connections

### Resources

DNS Spec root folder [RFC STD 13](https://www.rfc-editor.org/info/std13/)

Domain Names - Concepts and Facilites [RFC 1034](https://www.rfc-editor.org/info/rfc1034/)

Domain Names - Implementation and Spec [RFC 1035](https://www.rfc-editor.org/info/rfc1035/)

[Bitcoin Book - Bitcoin Network Section](https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch10_network.adoc)

[Message Structure](https://learnmeabitcoin.com/technical/general/compact-size/)