import socket
import sys
import threading

from struct import unpack

# import urllib.request
# from idl_parser import parser

# # response = urllib.request.urlopen("https://www.omg.org/spec/DDS-XRCE/20190301/dds_xrce_types.idl")
# # data = response.read()
# # xrce_idl = data.decode('utf-8')

# with open('xrce_idl', 'r') as file:
#     xrce_idl = file.read()

# parser_ = parser.IDLParser()
# global_module = parser_.load(xrce_idl)

# # for property, value in vars(global_module).items():
# #     print(property, ":", value)

# sys.exit(1)

fake_agent = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
fake_agent_port = 8888
real_agent_port = 8889
fake_agent.bind(("0.0.0.0", fake_agent_port))

fake_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)

client_address = None

submessage_types = {
    0: "CREATE_CLIENT",
    1: "CREATE",
    2: "GET_INFO",
    3: "DELETE",
    4: "STATUS_AGENT",
    5: "STATUS",
    6: "INFO",
    7: "WRITE_DATA",
    8: "READ_DATA",
    9: "DATA",
    10: "ACKNACK",
    11: "HEARTBEAT",
    12: "RESET",
    13: "FRAGMENT",
    14: "TIMESTAMP",
    15: "TIMESTAMP_REPLY"
}

object_types = {
    0: "DDS_XRCE_OBJK_INVALID",
    1: "DDS_XRCE_OBJK_PARTICIPANT",
    2: "DDS_XRCE_OBJK_TOPIC",
    3: "DDS_XRCE_OBJK_PUBLISHER",
    4: "DDS_XRCE_OBJK_SUBSCRIBER",
    5: "DDS_XRCE_OBJK_DATAWRITER",
    6: "DDS_XRCE_OBJK_DATAREADER",
    7: "DDS_XRCE_OBJK_REQUESTER",
    8: "DDS_XRCE_OBJK_REPLIER",
    10: "DDS_XRCE_OBJK_TYPE",
    11: "DDS_XRCE_OBJK_QOSPROFILE",
    12: "DDS_XRCE_OBJK_APPLICATION",
    13: "DDS_XRCE_OBJK_AGENT",
    14: "DDS_XRCE_OBJK_CLIENT",
    15: "DDS_XRCE_OBJK_OTHER"
}

fragment = b''

def decode_submessage(data):
    global fragment
    index = 0
    (submessageId, flags, submessageLength) = unpack('BBH', data[index:index+4])
    message_type = submessage_types[submessageId]
    print("  SUBMESSAGE {:s}".format(message_type))
    print("    submessageId: {:d}".format(submessageId))
    print("    flags: {:d}".format(flags))
    print("    submessageLength: {:d}".format(submessageLength))
    index = index + 4

    if message_type == "FRAGMENT":
        fragment = fragment + data[index:index+submessageLength]
        if flags & 0x2:
            print("*** FRAGMENT DECODED")
            print(fragment.hex())
            # decode_submessage(fragment)
            print("*** END FRAGMENT DECODED")
            fragment = b''

    elif message_type == "CREATE":
        (RequestId, ObjectId, ObjectKind) = unpack('HHB', data[index:index+5])
        index = index + 5
        print("    CREATE_KIND: {:s}".format(object_types[ObjectKind]))
    
    elif message_type == "HEARTBEAT":
        (first_unacked_seq_nr, last_unacked_seq_nr, stream_id) = unpack('HHB', data[index:index+5])
        index = index + 5
        print("    HEARTBEAT: I have unack from seq {:d} - {:d} on stream {:d}".format(first_unacked_seq_nr, last_unacked_seq_nr, stream_id))
    
    elif message_type == "ACKNACK":
        (first_unacked_seq_num, nack_bitmap, stream_id) = unpack('HHB', data[index:index+5])
        index = index + 5
        print("    ACKNACK: The next I want is {:d} mask {:d} on stream {:d}".format(first_unacked_seq_num, nack_bitmap, stream_id))
    
    index = index + submessageLength
    return (index, submessageLength)

def decode_msg(data):
    announced_size=4
    index = 0
    (sessionId, streamId, sequenceNr) = unpack('BBH', data[index:index+4])
    index = index + 4
    print("HEADER")
    print("  sessionId: {:d}".format(sessionId))
    print("  streamId: {:d}".format(streamId))
    print("  sequenceNr: {:d}".format(sequenceNr))
    if sessionId <= 127:
        announced_size = announced_size + 4
        print(data[index:index+4].hex())
        (clientKey) = unpack('I', data[index:index+4])
        print(type(clientKey))
        print("  clientKey: {:d}".format(clientKey))
        index = index + 4
    sunmessage_no = 0
    while(index < len(data) and len(data[index:]) > 4):
        (di, subm_len) = decode_submessage(data[index:])
        announced_size = announced_size + subm_len + 4
        index = index + di
    return announced_size


mutex = threading.Lock()

def fake_agent_thread():
    global client_address
    while True:
        if client_address is None:
            data, client_address = fake_agent.recvfrom(fake_agent_port)
        else:
            data, _ = fake_agent.recvfrom(fake_agent_port)
        mutex.acquire()
        print("\n-------- CLIENT -------- ({:d})".format(len(data)))
        # print(data.hex())
        header_calculated_size = decode_msg(data)
        if len(data) != header_calculated_size:
            print("EEEEERROR announced size: {:d}".format(header_calculated_size))
        mutex.release()
        fake_client.sendto(data, ("localhost", real_agent_port))

def fake_client_thread():
    global client_address
    while True:
        data, _ = fake_client.recvfrom(real_agent_port)
        mutex.acquire()
        print("\n-------- AGENT -------- ({:d})".format(len(data)))
        # print(data.hex())
        header_calculated_size = decode_msg(data)
        if len(data) != header_calculated_size:
            print("EEEEERROR announced size: {:d}".format(header_calculated_size))
        mutex.release()
        if client_address:
            fake_agent.sendto(data, client_address)


fagent = threading.Thread(target=fake_agent_thread)
fclient = threading.Thread(target=fake_client_thread)
fagent.start()
fclient.start()