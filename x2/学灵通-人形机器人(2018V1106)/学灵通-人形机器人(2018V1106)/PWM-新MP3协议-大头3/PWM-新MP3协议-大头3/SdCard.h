
//引用操作SD卡的相关函数

#include"CH376INC.h"

extern UINT8 xdata SdcardBuff[32]; //读取SD卡内文件的缓冲区

extern UINT8  CreateSdcardFile(PUINT8 TarFileName); //创建文件
extern UINT8  CH376FileOpenDir( PUINT8 PathName, UINT8 StopName ); //打开文件
extern UINT8  WriteSdcardFileBuffBytes(PUINT8 SrcFileName, UINT32	ByteCount);//往SD卡写入数据
extern UINT8  ReadSdcardFileAllBytes(PUINT8 SrcFileName); //从SD卡里读取某个文件的数据
extern UINT32	CH376ReadVar32( UINT8 var );                //VAR_FILE_SIZE-->指出读文件大小
extern UINT8	CH376ByteWrite(PUINT8 buf, UINT16 ReqCount, PUINT16 RealCount);
extern UINT8	CH376ByteRead(PUINT8 buf, UINT16 ReqCount, PUINT16 RealCount);
extern UINT8	CH376ByteLocate(UINT32 offset);
extern UINT32	CH376GetFileSize(void);
extern UINT8  CH376SendCmdDatWaitInt(UINT8 mCmd, UINT8 mDat);

extern UINT8 ReadSdcardFile32Bytes(PUINT8 SrcFileName);

extern void MP3_SetPlay(unsigned char mulu, unsigned char wenjian);
extern void MP3_Stop(void);