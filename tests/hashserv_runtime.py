import sys, os
os.chdir("/tmp")
sys.path.insert(0,'/opt/edf/sources/poky/bitbake/lib')
import hashserv
c=hashserv.create_client('unix:///hashserv/hashserv.sock')
method='edf-next-runtime-test'; taskhash='a'*64; outhash='b'*64; unihash='c'*64
if sys.argv[1]=='report':
    result=c.report_unihash(taskhash,method,outhash,unihash)
    assert result['unihash']==unihash,result
result=c.get_unihash(method,taskhash)
assert result==unihash,result
c.close()
print('PASS hashserv '+sys.argv[1]+': '+result)
