/****************************** (C) COPYRIGHT 2011 YQDZ **************************
* 文  件  名      : UART_HW.C
* 作      者      : 亿全电子
*                   FAE现场应用工程师 QQ:1027413631
*                   7*24小时技术支持电话:15366066738
*                   http://shop57138657.taobao.com/
* 版      本      : V1.0
* 日      期      : 2011/08/29
* 描      述      : 硬件标准异步串口连接CH376,提供I/O接口子程序.
*********************************************************************************/
#ifndef __CH376_DO_H__
#define __CH376_DO_H__

#include"CH376INC.h"

#define BuffLen 32          //缓冲区数据长度

UINT8	xdata	SdcardBuff[32]={0}; //读取SD卡内文件的缓冲区

/****** 本例中的硬件连接方式如下(实际应用电路可以参照修改下述定义及子程序) ******
					单片机的引脚    	CH376芯片的引脚
      					TXD                 RXD
      					RXD                 TXD    
*********************************************************************************/

//#define CH376_INT_WIRE			INT0												/* 假定CH376的INT#引脚,如果未连接那么也可以通过查询串口中断状态码实现 */

//#define	UART_INIT_BAUDRATE		9600											/* 默认通讯波特率9600bps,建议通过硬件引脚设定直接选择更高的CH376的默认通讯波特率 */
//#define	UART_WORK_BAUDRATE		115200										/* 正式通讯波特率57600bps */

/*******************************************************************************
* 函  数  名      : mDelayuS
* 描      述      : 延时指定微秒时间,根据单片机主频调整,不精确.
* 输      入      : 无.
* 返      回      : 无.
*******************************************************************************/
/*void mDelayuS(UINT8 us)  //@22.1184MHz
{
	unsigned char i;
	do{
		i = 3;
		while (--i);
	}while(--us);
} */

/*******************************************************************************
* 函  数  名      : mDelaymS
* 描      述      : 延时指定毫秒时间,根据单片机主频调整,不精确
* 输      入      : 无.
* 返      回      : 无.
*******************************************************************************/
/*void mDelaymS(UINT8 ms)
{
	while ( ms -- ) 
	{
		mDelayuS( 250 );
		mDelayuS( 250 );
		mDelayuS( 250 );
		mDelayuS( 250 );
	}
} */

/*******************************************************************************
* 函  数  名      : xWriteCH376Cmd
* 描      述      : 向CH376写命令.
* 输      入      : UINT8 mCmd:
*					要发送的命令.
* 返      回      : 无.
*******************************************************************************/
void xWriteCH376Cmd(UINT8 mCmd)
{
	IE2 = IE2 & 0xEF;
	
	CLR_TI4();
	S4BUF = SER_SYNC_CODE1;  			//启动操作的第1个串口同步码
	while(TI4L);
	CLR_TI4();
	S4BUF = SER_SYNC_CODE2;  			//启动操作的第2个串口同步码
	while(TI4L);
	CLR_TI4();
	S4BUF = mCmd;  								// 串口输出
	while(TI4L);
	CLR_TI4();
	
	IE2 = IE2 | 0x10;
}

/*******************************************************************************
* 函  数  名      : xWriteCH376Data
* 描      述      : 向CH376写数据.
* 输      入      : UINT8 mData
*					要发送的数据.
* 返      回      : 无.
*******************************************************************************/
void xWriteCH376Data(UINT8 mData)
{
	IE2 = IE2 & 0xEF;
	
	CLR_TI4();
	S4BUF = mData; 
	while(TI4L);
	CLR_TI4();
	
	IE2 = IE2 | 0x10;
}

/*******************************************************************************
* 函  数  名      : xReadCH376Data
* 描      述      : 从CH376读数据.
* 输      入      : 无.
* 返      回      : 接收到的数据.
*******************************************************************************/
UINT8	xReadCH376Data(void)
{
	UINT32	i;
	//UINT8   j;

	for(i = 0; i < 500000; i++) 									/* 计数防止超时 */
	{  
		if(RX4_flag == 1) 													/* 串口接收到 */
		{  
			RX4_flag = 0;			
			//j = RX4_Buffer[0];
			return(RX4_Buffer[0]);  									/* 串口输入 */
		}
	}

	return(0);  																	/* 不应该发生的情况 */
}

//==============================================================================
//设置CH376命令与数据，取返回状态码
UINT8 xSetCH376CmdData(UINT8 mCmd, UINT8 mData)
{
	UINT8	res;
	
	IE2 = IE2 & 0xEF;
	
	CLR_TI4();
	S4BUF = 0x57;  									/* 启动操作的第1个串口同步码 */
	while(TI4L);
	CLR_TI4();
	S4BUF = 0xAB;  									/* 启动操作的第2个串口同步码 */
	while(TI4L);
	CLR_TI4();
	S4BUF = mCmd;  									/* 命令 */
	while(TI4L);
	CLR_TI4();
	S4BUF = mData;  								/* 数据*/
	while(TI4L);
	CLR_TI4();	
	
	while(RI4L);
	CLR_RI4();
	res = S4BUF;                    //正确返回状态码
	
	IE2 = IE2 | 0x10;	
	
	return res;
}
//==============================================================================
//设置CH376命令，产生中断，取返回状态码
UINT8 xSetCH376Cmd(UINT8 mCmd)
{
	UINT8	res;
	
	IE2 = IE2 & 0xEF;
	
	CLR_TI4();
	S4BUF = 0x57;  															/* 启动操作的第1个串口同步码 */
	while(TI4L);
	CLR_TI4();
	S4BUF = 0xAB;  															/* 启动操作的第2个串口同步码 */
	while(TI4L);
	CLR_TI4();
	S4BUF = mCmd;  															/* 命令 */
	while(TI4L);
	CLR_TI4();	
	
	while(RI4L);
	CLR_RI4();
	res = S4BUF;                               //正确返回状态码
	
	IE2 = IE2 | 0x10;	
	
	return res;
}
/*******************************************************************************
* 函  数  名      : Query376Interrupt
* 描      述      : 查询CH376中断(INT#低电平).
* 输      入      : 无.
* 返      回      : FALSE：
*					没有中断.
*					TRUE:
*					有中断.
*******************************************************************************/
UINT8	Query376Interrupt(void)
{
	//UINT8 i;
#ifdef	CH376_INT_WIRE
	return( CH376_INT_WIRE ? FALSE : TRUE );  //如果连接了CH376的中断引脚则直接查询中断引脚
#else
	if (RX4_flag == 1) 
	{  																				// 如果未连接CH376的中断引脚则查询串口中断状态码
		RX4_flag = 0;
		//RX4_Buffer[0];
		return( TRUE );
	}
	else 
	{
		return( FALSE );
	}
#endif
} 
/*******************************************************************************
* 函  数  名      : mInitCH376Host
* 描      述      : 初始化CH376.
* 输      入      : 无.
* 返      回      : FALSE：
*					没有中断.
*					TRUE:
*					有中断.
*******************************************************************************/
UINT8	mInitCH376Host(void)
{
	UINT8	res;
	res = xSetCH376CmdData(0x06, 0x55); //测试单片机与CH376之间的通讯接口 正确返回状态码0xAA
	
	res = xSetCH376CmdData(0x15, 0x03); //设置工作模式  SD卡模式 正确返回状态码0x51
	
	res = xSetCH376Cmd(0x31);           //检测SD卡初始化成功否 0x14-->成功  0x82-->失败
	
	if(res == 0x14)
	{
		xWriteCH376Cmd(CMD21_SET_BAUDRATE); //重新设置通信波特率为115200bps
		xWriteCH376Data(0x03);
		xWriteCH376Data(0xCC);
		UART4_ResetBauteRate();             //再次设置单片机波特率
		res = xReadCH376Data();             //命令操作: 0x51-->成功  0x5F-->失败
	}	
	
	return res;

}

/*******************************************************************************
* 函  数  名      : CH376ReadBlock
* 描      述      : 从当前主机端点的接收缓冲区读取数据块,.
* 输      入      : PUINT8 buf:
*                   指向外部接收缓冲区.
* 返      回      : 返回长度.
*******************************************************************************/
UINT8	CH376ReadBlock( PUINT8 buf )
{
	UINT8	s, l;

	xWriteCH376Cmd( CMD01_RD_USB_DATA0 );
	s = l = xReadCH376Data( );  					//后续数据长度
	if ( l ) 
	{
		do 
		{
			*buf = xReadCH376Data( );
			buf ++;
		} while ( -- l );
	}	
	return( s );
}

/*******************************************************************************
* 函  数  名      : CH376WriteReqBlock
* 描      述      : 向内部指定缓冲区写入请求的数据块,返回长度.
* 输      入      : PUINT8 buf:
*                   指向发送缓冲区.
* 返      回      : UINT8 s：后续数据长度.
*******************************************************************************/
UINT8	CH376WriteReqBlock( PUINT8 buf )
{
	UINT8	s, l;

	xWriteCH376Cmd( CMD01_WR_REQ_DATA );   // 向内部指定缓冲区写入请求的数据块
	s = l = xReadCH376Data( );  	         //后续数据长度 
	if ( l ) 
	{
		do 
		{
			xWriteCH376Data( *buf );
			buf ++;
		} while ( -- l );
	}
	
	return( s );
} 

/*******************************************************************************
* 函  数  名      : CH376Read32bitDat
* 描      述      : 从CH376芯片读取32位的数据并结束命令.
* 输      入      : 无.
* 返      回      : 32位数据.
*******************************************************************************/
UINT32	CH376Read32bitDat( void )
{
	UINT8	c0, c1, c2, c3;

	c0 = xReadCH376Data( );
	c1 = xReadCH376Data( );
	c2 = xReadCH376Data( );
	c3 = xReadCH376Data( );	
	return( c0 | (UINT16)c1 << 8 | (UINT32)c2 << 16 | (UINT32)c3 << 24 );
}

/*******************************************************************************
* 函  数  名      : CH376ReadVar8
* 描      述      : 读CH376芯片内部的8位变量.
* 输      入      : 无.
* 返      回      : 8位变量.
*******************************************************************************/
UINT8	CH376ReadVar8( UINT8 var ) 
{
	UINT8	c0;
	
	xWriteCH376Cmd( CMD11_READ_VAR8 );                                                   /* 读取指定的8位文件系统变量 */
	xWriteCH376Data( var );
	c0 = xReadCH376Data( );	
	return( c0 );
}

/*******************************************************************************
* 函  数  名      : CH376WriteVar8
* 描      述      : 写CH376芯片内部的8位变量.
* 输      入      : UINT8 var：
*                   变量地址.
*                   UINT8 dat:
                    数据.
* 返      回      : 无.
*******************************************************************************/
void CH376WriteVar8( UINT8 var, UINT8 dat )
{
	xWriteCH376Cmd( CMD20_WRITE_VAR8 );      // 设置指定的8位文件系统变量 
	xWriteCH376Data( var );
	xWriteCH376Data( dat );	
}

/*******************************************************************************
* 函  数  名      : CH376ReadVar8
* 描      述      : 读CH376芯片内部的32位变量.
* 输      入      : UINT8 var：
*                   变量地址.
* 返      回      : 32位变量.
*******************************************************************************/
UINT32	CH376ReadVar32( UINT8 var )
{
	xWriteCH376Cmd( CMD14_READ_VAR32 );
	xWriteCH376Data( var );
	return( CH376Read32bitDat( ) ); //从CH376芯片读取32位的数据并结束命令												
}

/*******************************************************************************
* 函  数  名      : CH376WriteVar32
* 描      述      : 写CH376芯片内部的32位变量.
* 输      入      : UINT8 var：
*                   变量地址.
*					UINT32 dat:
*					数据.
* 返      回      : 无.
*******************************************************************************/
void	CH376WriteVar32( UINT8 var, UINT32 dat )
{
	xWriteCH376Cmd( CMD50_WRITE_VAR32 );
	xWriteCH376Data( var );
	xWriteCH376Data( (UINT8)dat );
	xWriteCH376Data( (UINT8)( (UINT16)dat >> 8 ) );
	xWriteCH376Data( (UINT8)( dat >> 16 ) );
	xWriteCH376Data( (UINT8)( dat >> 24 ) );	
}

/*******************************************************************************
* 函  数  名      : CH376EndDirInfo
* 描      述      : 在调用CH376DirInfoRead获取FAT_DIR_INFO结构之后应该通知CH376结束.
* 输      入      : 无.
* 返      回      : 无.
*******************************************************************************/
void	CH376EndDirInfo( void )
{
	CH376WriteVar8( 0x0D, 0x00 );
}

/*******************************************************************************
* 函  数  名      : CH376GetFileSize
* 描      述      : 读取当前文件长度.
* 输      入      : 无.
* 返      回      : 文件长度.
*******************************************************************************/
UINT32	CH376GetFileSize( void )
{
	return( CH376ReadVar32( VAR_FILE_SIZE ) );
}

/*******************************************************************************
* 函  数  名      : CH376GetDiskStatus
* 描      述      : 获取磁盘和文件系统的工作状态.
* 输      入      : 无.
* 返      回      : 状态.
*******************************************************************************/
UINT8	CH376GetDiskStatus( void )
{
	return( CH376ReadVar8( VAR_DISK_STATUS ) );
}

/*******************************************************************************
* 函  数  名      : CH376GetIntStatus
* 描      述      : 获取中断状态并取消中断请求.
* 输      入      : 无.
* 返      回      : UINT8 s:
*					中断状态.
*******************************************************************************/
UINT8	CH376GetIntStatus( void )
{
	UINT8	s;
	
	xWriteCH376Cmd( CMD01_GET_STATUS );
	s = xReadCH376Data( );	
	return( s );
}

/*******************************************************************************
* 函  数  名      : Wait376Interrupt
* 描      述      : 等待CH376中断(INT#低电平)，返回中断状态码, 超时则返回
*                   ERR_USB_UNKNOWN.
* 输      入      : 无.
* 返      回      : 中断状态.
*******************************************************************************/
#ifndef	NO_DEFAULT_CH376_INT
UINT8	Wait376Interrupt( void )
{
#ifdef	DEF_INT_TIMEOUT                                      // 是否定义了超时时间 
#if		DEF_INT_TIMEOUT < 1                                    // 没有定义 
	while ( Query376Interrupt( ) == FALSE );                   // 一直等中断 
	return( CH376GetIntStatus( ) );                            // 检测到中断 
#else                                                        // 定义了超时时间 
	UINT32	i;
	
	for ( i = 0; i < DEF_INT_TIMEOUT; i ++ )                    // 计数防止超时
	{  
		if ( Query376Interrupt( ) ) 
		{
		    return( CH376GetIntStatus( ) );                       // 检测到中断
		}
        //在等待CH376中断的过程中,可以做些需要及时处理的其它事情 
	}
	return( ERR_USB_UNKNOWN );                                 // 不应该发生的情况
#endif
#else
	UINT32	i;
	
	for ( i = 0; i < 5000000; i ++ )                          // 计数防止超时,默认的超时时间,与单片机主频有关 
	{  
		if ( Query376Interrupt( ) ) 
		{
		    return( CH376GetIntStatus( ) );                    // 检测到中断
		}
        // 在等待CH376中断的过程中,可以做些需要及时处理的其它事情
	}
	return( ERR_USB_UNKNOWN );                               // 不应该发生的情况
#endif
}
#endif

/*******************************************************************************
* 函  数  名      : CH376SendCmdWaitInt
* 描      述      : 发出命令码后,等待中断.
* 输      入      : UINT8 mCmd:
*					命令码.
* 返      回      : 中断状态.
*******************************************************************************/
UINT8	CH376SendCmdWaitInt( UINT8 mCmd )
{
	xWriteCH376Cmd( mCmd );
	return( Wait376Interrupt( ) );
}

/*******************************************************************************
* 函  数  名      : CH376SendCmdDatWaitInt
* 描      述      : 发出命令码和一字节数据后,等待中断.
* 输      入      : 无.
* 返      回      : 中断状态.
*******************************************************************************/
UINT8	CH376SendCmdDatWaitInt( UINT8 mCmd, UINT8 mDat )
{
	xWriteCH376Cmd( mCmd );
	xWriteCH376Data( mDat );
	return( Wait376Interrupt( ) );
}

/*******************************************************************************
* 函  数  名      : CH376DiskReqSense
* 描      述      : 检查USB存储器错误.
* 输      入      : 无.
* 返      回      : UINT8 s:
*					状态.
*******************************************************************************/
/*UINT8	CH376DiskReqSense( void )
{
	UINT8	s;

	mDelaymS( 5 );
	s = CH376SendCmdWaitInt( CMD0H_DISK_R_SENSE );
	mDelaymS( 5 );
	return( s );
}  */

/*******************************************************************************
* 函  数  名      : CH376DiskConnect
* 描      述      : 检查U盘是否连接,不支持SD卡.
* 输      入      : 无.
* 返      回      : U盘是否连接状态.
*******************************************************************************/
/*UINT8	CH376DiskConnect( void )
{
	if ( Query376Interrupt( ) ) 
	{
		CH376GetIntStatus( );  															// 检测到中断,获取中断状态
	}
	return( CH376SendCmdWaitInt( CMD0H_DISK_CONNECT ) );	// 检查磁盘是否连接
}  */

/*******************************************************************************
* 函  数  名      : CH376DiskMount
* 描      述      : 初始化磁盘并测试磁盘是否就绪.
* 输      入      : 无.
* 返      回      : 中断状态.
*******************************************************************************/
/*UINT8 CH376DiskMount( void )
{
	return( CH376SendCmdWaitInt( CMD0H_DISK_MOUNT ) );	//初始化磁盘并测试磁盘是否就绪
} */

/*******************************************************************************
* 函  数  名      : CH376SetFileName
* 描      述      : 设置将要操作的文件的文件名 .
* 输      入      : PUINT8 name：
*					指向文件名缓冲区.
* 返      回      : 无.
*******************************************************************************/
void	CH376SetFileName( PUINT8 name )
{
	UINT8	c;

#ifndef	DEF_IC_V43_U																	/* 默认支持低版本 */
	UINT8	s;
	UINT8   i;

	xWriteCH376Cmd( CMD01_GET_IC_VER );									/* 获取芯片版本 */
	i = xReadCH376Data( );

	if (  i < 0x43 ) 
	{
		if ( CH376ReadVar8( VAR_DISK_STATUS ) < DEF_DISK_READY ) 
		{
			xWriteCH376Cmd( CMD10_SET_FILE_NAME );
			xWriteCH376Data( 0 );
			s = CH376SendCmdWaitInt( CMD0H_FILE_OPEN );
			if ( s == USB_INT_SUCCESS ) 
			{
				s = CH376ReadVar8( 0xCF );
				if ( s ) 
				{
					CH376WriteVar32( 0x4C, CH376ReadVar32( 0x4C ) + ( (UINT16)s << 8 ) );
					CH376WriteVar32( 0x50, CH376ReadVar32( 0x50 ) + ( (UINT16)s << 8 ) );
					CH376WriteVar32( 0x70, 0 );
				}
			}
		}
	}
#endif
	xWriteCH376Cmd( CMD10_SET_FILE_NAME );
	c = *name;
	xWriteCH376Data( c );
	while ( c ) 
	{
		name ++;
		c = *name;
		if ( c == DEF_SEPAR_CHAR1 || c == DEF_SEPAR_CHAR2 ) 
		{
			c = 0;  																	/* 强行将文件名截止 */
		}
		xWriteCH376Data( c );
	}	
}

/*******************************************************************************
* 函  数  名      : CH376FileOpen
* 描      述      : 在根目录或者当前目录下打开文件或者目录(文件夹).
* 输      入      : 无.
* 返      回      : 中断状态.
*******************************************************************************/
UINT8	CH376FileOpen( PUINT8 name ) 
{
	CH376SetFileName( name );  												//设置将要操作的文件的文件名
#ifndef	DEF_IC_V43_U
	if( name[0] == DEF_SEPAR_CHAR1 || name[0] == DEF_SEPAR_CHAR2 ) 
	{
		CH376WriteVar32( VAR_CURRENT_CLUST, 0 );
	}
#endif
	return( CH376SendCmdWaitInt( CMD0H_FILE_OPEN ) );
} 

/*******************************************************************************
* 函  数  名      : CH376FileCreate
* 描      述      : 在根目录或者当前目录下新建文件,如果文件已经存在那么先删除.
* 输      入      : 无.
* 返      回      : 中断状态.
*******************************************************************************/
UINT8	CH376FileCreate( PUINT8 name )
{
	if ( name ) 
	{
		CH376SetFileName( name );  													//设置将要操作的文件的文件名
	}
	return( CH376SendCmdWaitInt( CMD0H_FILE_CREATE ) );
}

/*******************************************************************************
* 函  数  名      : CH376DirCreate
* 描      述      : 在根目录下新建目录(文件夹)并打开,如果目录已经存在那么直接打开.
* 输      入      : 无.
* 返      回      : 中断状态.
*******************************************************************************/
/*UINT8	CH376DirCreate( PUINT8 name )
{
	CH376SetFileName( name );  														//设置将要操作的文件的文件名
#ifndef	DEF_IC_V43_U
	if ( name[0] == DEF_SEPAR_CHAR1 || name[0] == DEF_SEPAR_CHAR2 ) 
	{
		CH376WriteVar32( VAR_CURRENT_CLUST, 0 );
	}
#endif
	return( CH376SendCmdWaitInt( CMD0H_DIR_CREATE ) );
}
*/
/*******************************************************************************
* 函  数  名      : CH376SeparatePath
* 描      述      : 从路径中分离出最后一级文件名或者目录(文件夹)名
* 输      入      : PUINT8 path:
*					指向路径缓冲区.
* 返      回      : 返回最后一级文件名或者目录名的字节偏移.
*******************************************************************************/
UINT8	CH376SeparatePath( PUINT8 path )
{
	PUINT8	pName;

	for ( pName = path; *pName != 0; ++ pName );  	// 到文件名字符串结束位置
	while ( *pName != DEF_SEPAR_CHAR1 && *pName != DEF_SEPAR_CHAR2 && pName != path ) 
	{	
		pName --;  																		//  搜索倒数第一个路径分隔符
	}
	if ( pName != path ) 
	{
		pName ++;  																		// 找到了路径分隔符,则修改指向目标文件的最后一级文件名,跳过前面的多级目录名及路径分隔符
	}
	return( pName - path );
}

/*******************************************************************************
* 函  数  名      : CH376FileOpenDir
* 描      述      : 打开多级目录下的文件或者目录的上级目录,支持多级目录路径,
*					支持路径分隔符,路径长度不超过255个字符
* 输      入      : PUINT8 path:
*					指向路径缓冲区.
*					UINT8 StopName:
*					指向最后一级文件名或者目录名
* 返      回      : 返回最后一级文件名或者目录名的字节偏移.
*******************************************************************************/
UINT8	CH376FileOpenDir( PUINT8 PathName, UINT8 StopName )
{
	UINT8	i, s;

	s = 0;
	i = 1;  																			/* 跳过有可能的根目录符 */
	while ( 1 ) 
	{
		while ( PathName[i] != DEF_SEPAR_CHAR1 && PathName[i] != DEF_SEPAR_CHAR2 && PathName[i] != 0 ) 
		{
			++ i;  																		/* 搜索下一个路径分隔符或者路径结束符 */
		}

		if ( PathName[i] ) 
		{
			i ++;  																		/* 找到了路径分隔符,修改指向目标文件的最后一级文件名 */
		}
		else 
		{
			i = 0;  																	/* 路径结束 */
		}
		
		s = CH376FileOpen( &PathName[s] );  				/* 打开文件或者目录 */
		
		if ( i && i != StopName ) 									/* 路径尚未结束 */	
		{  			
			if ( s != ERR_OPEN_DIR ) 									/* 因为是逐级打开,尚未到路径结束,所以,如果不是成功打开了目录,那么说明有问题 */
			{  
				if ( s == USB_INT_SUCCESS ) 
				{
					return( ERR_FOUND_NAME );  						/* 中间路径必须是目录名,如果是文件名则出错 */
				}
				else if ( s == ERR_MISS_FILE ) 
				{
					return( ERR_MISS_DIR );  							/* 中间路径的某个子目录没有找到,可能是目录名称错误 */
				}
				else 
				{
					return( s );  												/* 操作出错 */
				}
			}
			s = i;  																	/* 从下一级目录开始继续 */
		}
		else 
		{
			return( s ); /* 路径结束,USB_INT_SUCCESS为成功打开文件,ERR_OPEN_DIR为成功打开目录(文件夹),其它为操作出错 */
		}
	}
}

/*******************************************************************************
* 函  数  名      : CH376FileOpenPath
* 描      述      : 打开多级目录下的文件或者目录(文件夹),支持多级目录路径,
*					支持路径分隔符,路径长度不超过255个字符
* 输      入      : PUINT8 path:
*					指向路径缓冲区.
* 返      回      : 返回最后一级文件名或者目录名的字节偏移.
*******************************************************************************/
/*UINT8	CH376FileOpenPath( PUINT8 PathName )
{
	return( CH376FileOpenDir( PathName, 0xFF ) );
} 
*/
/*******************************************************************************
* 函  数  名      : CH376ByteLocate
* 描      述      : 以字节为单位移动当前文件指针
* 输      入      : UINT32 offset:
*					指针偏移地址.
* 返      回      : 中断状态.
*******************************************************************************/
UINT8	CH376ByteLocate( UINT32 offset )
{
	xWriteCH376Cmd( CMD4H_BYTE_LOCATE );
	xWriteCH376Data( (UINT8)offset );
	xWriteCH376Data( (UINT8)((UINT16)offset>>8) );
	xWriteCH376Data( (UINT8)(offset>>16) );
	xWriteCH376Data( (UINT8)(offset>>24) );
	
	return( Wait376Interrupt( ) );
}

/*******************************************************************************
* 函  数  名      : CH376ByteRead
* 描      述      : 以字节为单位从当前位置读取数据块
* 输      入      : PUINT8 buf:
*					指向数据缓冲区.
*                   UINT16 ReqCount：
*                   请求读取的字节数.
*                   PUINT16 RealCount:
*                   实际读取的字节数.
* 返      回      : 中断状态.
*******************************************************************************/
UINT8	CH376ByteRead( PUINT8 buf, UINT16 ReqCount, PUINT16 RealCount )
{
	UINT8	s;
	
	xWriteCH376Cmd( CMD2H_BYTE_READ );
	xWriteCH376Data( (UINT8)ReqCount );
	xWriteCH376Data( (UINT8)(ReqCount>>8) );
	
	if( RealCount ) 
	{
	    *RealCount = 0;
	}
	
	while( 1 ) 
	{
		s = Wait376Interrupt( );
		if( s == USB_INT_DISK_READ )                                 //请求数据读出
		{
			s = CH376ReadBlock( buf );                                  //从当前主机端点的接收缓冲区读取数据块,返回长度 
			xWriteCH376Cmd( CMD0H_BYTE_RD_GO );                         // 继续读 
			
			buf += s;
			if ( RealCount ) 
			{
			    *RealCount += s;
			}
		}
		else 
		{
		    return( s );                                              // 错误
		}
	}
	
}

/*******************************************************************************
* 函  数  名      : CH376ByteWrite
* 描      述      : 以字节为单位向当前位置写入数据块.
* 输      入      : PUINT8 buf:
*					指向外部缓冲区.
*                   UINT16 ReqCount：
*                   请求写入的字节数.
*                   PUINT16 RealCount:
*                   实际写入的字节数.
* 返      回      : 中断状态.
*******************************************************************************/
UINT8	CH376ByteWrite( PUINT8 buf, UINT16 ReqCount, PUINT16 RealCount )
{
	UINT8	s;
	
	xWriteCH376Cmd( CMD2H_BYTE_WRITE );
	xWriteCH376Data( (UINT8)ReqCount );
	xWriteCH376Data( (UINT8)(ReqCount>>8) );
	
	if ( RealCount ) 
    {
        *RealCount = 0;
    }
	
	while ( 1 ) 
	{
		s = Wait376Interrupt( );
		if ( s == USB_INT_DISK_WRITE ) 
		{
			s = CH376WriteReqBlock( buf );           //向内部指定缓冲区写入请求的数据块,返回长度
			xWriteCH376Cmd( CMD0H_BYTE_WR_GO );
			
			buf += s;
			if ( RealCount ) *RealCount += s;
		}
		else 
	    {
	        return( s );                         // 错误
	    }
	}
} 

/*******************************************************************************
* 函  数  名      : CH376FileClose
* 描      述      : 关闭当前已经打开的文件或者目录(文件夹)
* 输      入      : PUINT8 UpdateSz:
*					是否更新文件长度.
* 返      回      : 中断状态.
*******************************************************************************/
/*UINT8	CH376FileClose( UINT8 UpdateSz )
{
	return( CH376SendCmdDatWaitInt( CMD1H_FILE_CLOSE, UpdateSz ) );
} */

/*******************************************************************************
* 函  数  名      : CopyAndConvertFile
* 描      述      : 文件复制,以字节方式复制,缓冲区越大速度越快.
* 输      入      : PUINT8 SrcFileName：
*                   源文件名,支持路径分隔符和多级目录,字符串必须存放于RAM中
*                   PUINT8 TarFileName 
*                   目标文件名,支持路径分隔符和多级目录,字符串必须存放于RAM中
* 返      回      : 无.
*******************************************************************************/
/*UINT8	CopyAndConvertFile(PUINT8 SrcFileName, PUINT8 TarFileName) 
{ 
	UINT8	  s;
	UINT16	ThisLen, cnt;
	UINT32	FileSize, ByteCount = 0;
	UINT8	  TarName;
	UINT32	TarUpDirClust;	
	
	do 
	{
		s = CH376FileOpenPath(SrcFileName);      // 打开多级目录下的文件,输入缓冲区必须在RAM中
		if(s != USB_INT_SUCCESS) 
			return(s);
		
		if(ByteCount == 0)                       // 首次 
		{  
			FileSize = CH376GetFileSize();         // 读取当前文件长度 		
		}
		else                                     // 再次进入
	  {  
			s = CH376ByteLocate(ByteCount);        // 以字节为单位移动当前文件指针到上次复制结束位置			
			if(s != USB_INT_SUCCESS) 
				return(s);
		}
		
		s = CH376ByteRead(SdcardBuff, sizeof(SdcardBuff), &ThisLen);// 以字节为单位从当前位置读取数据块,请求长度同缓冲区大小,返回实际长度在ThisLen中
		if(s != USB_INT_SUCCESS)
			return(s);

		for ( cnt = 0; cnt < ThisLen; cnt++ )         // 将缓冲区中的小写字符转换为大写
		{  
			s = SdcardBuff[ cnt ];
			if ( s >= 'a' && s <= 'z' ) 
			{
			    SdcardBuff[ cnt ] = s - ( 'a' - 'A' );
			}
		}

		if ( ByteCount == 0 )                              // 首次,目标文件尚未存在
		{  
			TarName = CH376SeparatePath( TarFileName );      // 从路径中分离出最后一级文件名或目录名,返回最后一级文件名或目录名的偏移 
			if ( TarName )                                   // 是多级目录 
			{  
				s = CH376FileOpenDir( TarFileName, TarName );  // 打开多级目录下的最后一级目录,即打开新建文件的上级目录
				if ( s != ERR_OPEN_DIR )                       // 因为是打开上级目录,所以,如果不是成功打开了目录,那么说明有问题
				{  
					if ( s == USB_INT_SUCCESS ) 
					{
					    return( ERR_FOUND_NAME );                // 中间路径必须是目录名,如果是文件名则出错
					}
					else if ( s == ERR_MISS_FILE ) 
					{
					    return( ERR_MISS_DIR );                 // 中间路径的某个子目录没有找到,可能是目录名称错误
					}
					else
					{ 
					    return( s );                            // 操作出错
					}
				}
				TarUpDirClust = CH376ReadVar32( VAR_START_CLUSTER );    // 上级目录的起始簇号
			}
			else 
			{
			    TarUpDirClust = 0;                                    // 默认是根目录的起始簇号
			}
*/			
   /* 在当前目录下进行文件新建或者打开操作,比全路径多级目录下的文件新建或者打开操作的速度快,
   所以目标文件的新建或者打开采用此法处理(本程序源文件是直接打开全路径多级目录下的文件,为提高速度,也可参照此法加快文件打开),
   为了实现当前目录下的文件新建或者打开操作,参考上面几行代码,
   首先,要获得文件所在的上级目录的起始簇号,相当于打开上级目录,通过CH376FileOpenPath打开上级目录获得,
   其次,要获得文件的直接短文件名(去掉上级目录名,不含任何路径分隔符,保留最后一级文件名),通过CH376SeparatePath分析目标文件名获得 */
/*			s = CH376FileCreate( &TarFileName[TarName] );// 在根目录或者当前目录下新建文件,如果文件已经存在那么先删除 
			if ( s != USB_INT_SUCCESS ) 
		  {
		        return( s );
		  }
		}
		else                                                     // 再次进入,目标文件已存在
		{  
			CH376WriteVar32( VAR_START_CLUSTER, TarUpDirClust );   // 将目标文件所在的上级目录的起始簇号设置为当前簇号,相当于打开上级目录
			s = CH376FileOpen( &TarFileName[TarName] );            // 打开文件
			if ( s != USB_INT_SUCCESS ) 
			{
			    return( s );
			}
			
			s = CH376ByteLocate( ByteCount );                     // 以字节为单位移动当前文件指针到上次复制结束位置
			if ( s != USB_INT_SUCCESS ) 
			{
			    return( s );
			}
		}
		
		s = CH376ByteWrite( SdcardBuff, ThisLen, NULL );       // 以字节为单位向当前位置写入数据块,除非没有磁盘空间,否则返回实际长度总是与ThisLen相等
		if ( s != USB_INT_SUCCESS ) 
		{
		    return( s );
		}

		s = CH376FileClose( TRUE );                             // 关闭文件,对于字节读写建议自动更新文件长度 
		if ( s != USB_INT_SUCCESS ) 
		{
		    return( s );
		}
		
		ByteCount += ThisLen;
		
		if ( ThisLen < sizeof( SdcardBuff ) )                    // 实际读出字节数小于请求读出字节数,说明原文件结束
		{  
			break;
		}
		
	} while( ByteCount < FileSize );
	
	return( USB_INT_SUCCESS );
}  */

//==============================================================================
//创建SD卡内单个文件
//TarFileName(文件绝对路径)
UINT8 CreateSdcardFile(PUINT8 TarFileName)
{
	UINT8	  s;
	UINT8	  TarName;
	UINT32	TarUpDirClust;
	
	TarName = CH376SeparatePath( TarFileName );       /* 从路径中分离出最后一级文件名或目录名,返回最后一级文件名或目录名的偏移 */
	if( TarName )                                     /* 是多级目录 */
	{  
		s = CH376FileOpenDir( TarFileName, TarName );  /* 打开多级目录下的最后一级目录,即打开新建文件的上级目录 */
		if(s != ERR_OPEN_DIR)                          /* 因为是打开上级目录,所以,如果不是成功打开了目录,那么说明有问题 */
		{  
			if ( s == USB_INT_SUCCESS ) 
			{
					return( ERR_FOUND_NAME );                /* 中间路径必须是目录名,如果是文件名则出错 */
			}
			else if ( s == ERR_MISS_FILE ) 
			{
					return( ERR_MISS_DIR );                  /* 中间路径的某个子目录没有找到,可能是目录名称错误 */
			}
			else
			{ 
					return( s );                             /* 操作出错 */
			}
		}
		TarUpDirClust = CH376ReadVar32( VAR_START_CLUSTER );    /* 上级目录的起始簇号 */
	}
	else 
	{
			TarUpDirClust = 0;                                    /* 默认是根目录的起始簇号 */
	}
	/* 在当前目录下进行文件新建或者打开操作,比全路径多级目录下的文件新建或者打开操作的速度快,
	所以目标文件的新建或者打开采用此法处理(本程序源文件是直接打开全路径多级目录下的文件,为提高速度,也可参照此法加快文件打开),
	为了实现当前目录下的文件新建或者打开操作,参考上面几行代码,
	首先,要获得文件所在的上级目录的起始簇号,相当于打开上级目录,通过CH376FileOpenPath打开上级目录获得,
	其次,要获得文件的直接短文件名(去掉上级目录名,不含任何路径分隔符,保留最后一级文件名),通过CH376SeparatePath分析目标文件名获得 */
	s = CH376FileCreate( &TarFileName[TarName] );/* 在根目录或者当前目录下新建文件,如果文件已经存在那么先删除 */
	if(s != USB_INT_SUCCESS) 
	{
				return( s );
	}
	
	//s = CH376FileClose( TRUE );  //关闭文件,对于字节读写建议自动更新文件长度
	s = CH376SendCmdDatWaitInt( CMD1H_FILE_CLOSE, TRUE );
	if(s != USB_INT_SUCCESS) 	
	{
			return( s );
	} 
	
	return ( s );
}

//==============================================================================
//往SD卡内单个文件里写入缓冲区的数据
//缓冲区: SdcardBuff  缓冲区大小: BuffLen
//SrcFileName(文件绝对路径)  ByteCount(写入位置的地址)
UINT8 WriteSdcardFileBuffBytes(PUINT8 SrcFileName, UINT32	ByteCount)
{
	UINT8	  s;
	 
	//s = CH376FileOpenPath(SrcFileName);              /* 打开多级目录下的文件,输入缓冲区必须在RAM中 */
	s = CH376FileOpenDir( SrcFileName, 0xFF );
	if(s != USB_INT_SUCCESS) 
		return(s);
	
	s = CH376ByteLocate( ByteCount );                  /* ByteCount 以字节为单位移动当前文件指针到上次复制结束位置 */
	if(s != USB_INT_SUCCESS)
		return(s);	 
	
	s = CH376ByteWrite( SdcardBuff, BuffLen, NULL );  /* 以字节为单位向当前位置写入数据块,除非没有磁盘空间,否则返回实际长度总是与ThisLen相等 */
	if(s != USB_INT_SUCCESS)
		return( s );

	//s = CH376FileClose( TRUE );  //关闭文件,对于字节读写建议自动更新文件长度
	s = CH376SendCmdDatWaitInt( CMD1H_FILE_CLOSE, TRUE );
	if(s != USB_INT_SUCCESS)
		return( s ); 
		
	return( s );
}

//==============================================================================
//读取SD卡内单个文件的所有字节, 并且通过串口1上传
//SrcFileName(文件绝对路径) 
UINT8 ReadSdcardFileAllBytes(PUINT8 SrcFileName)
{
	UINT8	  s;
	UINT16	ThisLen;
	UINT32	FileSize, ByteCount = 0;
	
	do 
	{
		//s = CH376FileOpenPath(SrcFileName);      /* 打开多级目录下的文件,输入缓冲区必须在RAM中 */
		s = CH376FileOpenDir( SrcFileName, 0xFF );
		if(s != USB_INT_SUCCESS) 
			return(s);
		
		if(ByteCount == 0)                       /* 首次 */
		{  
			FileSize = CH376GetFileSize();         /* 读取当前文件长度 */			
		}
		else                                     /* 再次进入 */ 
	  {  
			s = CH376ByteLocate(ByteCount);        /* 以字节为单位移动当前文件指针到上次复制结束位置 */			
			if(s != USB_INT_SUCCESS) 
				return(s);
		}
		
		s = CH376ByteRead(SdcardBuff, sizeof(SdcardBuff), &ThisLen);/* 以字节为单位从当前位置读取数据块,请求长度同缓冲区大小,返回实际长度在ThisLen中 */
		if(s != USB_INT_SUCCESS)
			return(s);

		ByteCount += ThisLen;
		
		UART1_PrintArrayBytes(SdcardBuff, ThisLen); //串口1输出显示+++++++++++++++++++
		
		if( ThisLen < sizeof( SdcardBuff ) )       /* 实际读出字节数小于请求读出字节数,说明原文件结束 */
		{  
			break;
		}
		
	} while( ByteCount < FileSize );
	
	//s = CH376FileClose( TRUE );  //关闭文件,对于字节读写建议自动更新文件长度
	s = CH376SendCmdDatWaitInt( CMD1H_FILE_CLOSE, TRUE );
	if ( s != USB_INT_SUCCESS ) 	
	{
			return( s );
	} 
	
	return( USB_INT_SUCCESS );		
}

//==============================================================================
//只读取SD卡内单个文件的前32字节, 不上传
//SrcFileName(文件绝对路径) 
UINT8 ReadSdcardFile32Bytes(PUINT8 SrcFileName)
{
	UINT8	  s;
	UINT16	ThisLen;
	
	//s = CH376FileOpenPath(SrcFileName);      /* 打开多级目录下的文件,输入缓冲区必须在RAM中 */
	s = CH376FileOpenDir(SrcFileName, 0xFF);
	if(s != USB_INT_SUCCESS) 
		return(s);

	s = CH376ByteLocate(0);                   /* 以字节为单位移动当前文件指针到上次复制结束位置 */			
	if(s != USB_INT_SUCCESS) 
		return(s);
	
	s = CH376ByteRead(SdcardBuff, sizeof(SdcardBuff), &ThisLen);/* 以字节为单位从当前位置读取数据块,请求长度同缓冲区大小,返回实际长度在ThisLen中 */
	if(s != USB_INT_SUCCESS)
		return(s);
	
	//s = CH376FileClose( TRUE );  //关闭文件,对于字节读写建议自动更新文件长度
	s = CH376SendCmdDatWaitInt( CMD1H_FILE_CLOSE, TRUE );
	if(s != USB_INT_SUCCESS)
			return(s);
	
	return( USB_INT_SUCCESS );		
}





#endif
/************************************ End *************************************/