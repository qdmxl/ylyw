
/*------------------------------------------------------------------*/
/* --- STC MCU International Limited -------------------------------*/
/* --- STC 1T Series MCU RC Demo -----------------------------------*/
/* If you want to use the program or the program referenced in the  */
/* article, please specify in which data and procedures from STC    */
/*------------------------------------------------------------------*/

#ifndef __USART_H__
#define __USART_H__ 

//#define  MAIN_Fosc		24000000L	//定义主时钟
//#define	 BaudRate		9600UL	//选择波特率
//#define	 Timer2_Reload	(65536UL -(MAIN_Fosc / 4 / BaudRate))

#define	 TI2			(S2CON & 2) != 0
#define	 TI2L			(S2CON & 2) == 0
#define	 RI2			(S2CON & 1) != 0
#define	 SET_TI2()	    S2CON |=  2
#define	 CLR_TI2()	    S2CON &= ~2
#define	 CLR_RI2()	    S2CON &= ~1

#define	 TI3			(S3CON & 2) != 0
#define	 TI3L			(S3CON & 2) == 0
#define	 RI3			(S3CON & 1) != 0
#define	 SET_TI3()	    S3CON |=  2
#define	 CLR_TI3()	    S3CON &= ~2
#define	 CLR_RI3()	    S3CON &= ~1

#define	 TI4			(S4CON & 2) != 0
#define	 TI4L			(S4CON & 2) == 0
#define	 RI4			(S4CON & 1) != 0
#define	 RI4L			(S4CON & 1) == 0
#define	 SET_TI4()	    S4CON |=  2
#define	 CLR_TI4()	    S4CON &= ~2
#define	 CLR_RI4()	    S4CON &= ~1

#define  COM_TX1_Lenth	1
#define  COM_RX1_Lenth	400
#define  COM_TX2_Lenth	1
#define  COM_RX2_Lenth	16
#define  COM_TX3_Lenth	1
#define  COM_RX3_Lenth	1
#define  COM_TX4_Lenth	1
#define  COM_RX4_Lenth	1

unsigned int in = 0;  //串口1接收计数
unsigned int out = 0;
bit RX1_flag = 0;
bit RX1_mode = 0;     //串口1接收模式
//u8 RX1_in = 0;      //串口1接收计数

bit RX2_flag = 0;
u8 RX2_in = 0;     //串口2接收计数
u16 RX2_Key = 0;

//bit RX3_flag = 0;
//u8 RX3_in = 0;     //串口3接收计数

bit RX4_flag = 0;   //串口4控制接收标志
//u8 RX4_in = 0;      //串口4接收计数

//u8	xdata TX1_Buffer[COM_TX1_Lenth];	//发送缓冲
u8 	xdata RX1_Buffer[COM_RX1_Lenth]={0};	//接收缓冲

//u8	xdata TX2_Buffer[COM_TX2_Lenth];	//发送缓冲
u8 	xdata RX2_Buffer[COM_RX2_Lenth]={0};	//接收缓冲

//u8	xdata TX3_Buffer[COM_TX3_Lenth];	//发送缓冲
u8 	xdata RX3_Buffer[COM_RX3_Lenth]={0};	//接收缓冲

//u8	xdata TX4_Buffer[COM_TX4_Lenth];	//发送缓冲
u8 	xdata RX4_Buffer[COM_RX4_Lenth]={0};	//接收缓冲

void Uart_Init(void)      //晶振频率: 22.1184MHz
{
	P_SW2 |= 0x07;  //切换端口

	SCON = 0x50;		//8位数据,可变波特率 串口1与串口2同使用T2做波特率发生器
	S2CON = 0x50;		//8位数据,可变波特率
	
	S3CON = 0x10;		//8位数据,可变波特率
	S3CON &= 0xBF;	//串口3选择定时器2为波特率发生器
	
	S4CON = 0x10;		 //8位数据,可变波特率
	//S4CON &= 0xBF;	//串口4选择定时器2为波特率发生器
	S4CON |= 0x40;	 //串口4选择定时器4为波特率发生器
	T4T3M |= 0x20;	 //定时器4时钟为Fosc,即1T
	T4L = 0xE0;		   //设定定时初值  上电默认9600bps--->串口4用于SD卡存储操作
	T4H = 0xFE;		   //设定定时初值
	T4T3M |= 0x80;	 //启动定时器4	

	AUXR &= ~(1<<4);	//Timer stop    波特率使用Timer2产生
	AUXR |= 0x01;		  //串口1选择定时器2为波特率发生器
	AUXR |= 0x04;		  //定时器2时钟为Fosc,即1T
	
	T2L = 0xE0;		   //0xC0设定定时初值  9600bps----->串口1、2、3同用
	T2H = 0xFE;		   //0xFD设定定时初值

	AUXR |= 0x10;		//启动定时器2

	ES = 1;				  //ES1            开启中断
	IE2 |= 0x19;    //ES4  ES3  ES2  开启中断
}

//=============================================================================
void UART4_ResetBauteRate(void) //设置读取SD卡的通信波特率
{
	T4T3M &= 0x7F;	 //停止定时器4
	T4L = 0xE8;		   //0xD0设定定时初值  115200bps--->串口4用于SD卡存储操作
	T4H = 0xFF;		   //0xFF
	T4T3M |= 0x80;	 //启动定时器4
}

//=============================================================================
void UART1_PrintString(u8 *str)    //串口 1 发送字符串数据
{
	TI = 0;
	while(*str != '\0')
	{
		SBUF = *str;
		while(TI == 0);
		TI = 0;
		str++;
	}
}
//=============================================================================
void UART1_PrintArrayBytes(u8 *str, u16 len)    //串口 1 发送数组数据
{ 
	unsigned int i = 0;
	TI = 0;
	while(i != len)
	{
		SBUF = *str;
		while(TI == 0);
		TI = 0;
		str++;
		i++;
	}
} 
//=============================================================================
void UART1_PrintByte(u8 value)     //串口 1 发送单字节
{
	TI = 0;
	SBUF = value;
	while(TI == 0);
	TI = 0;
}

//=============================================================================
/*void UART2_PrintByte(u8 value)     //串口 2 发送单字节
{
	IE2 = IE2 & 0xFE;
	CLR_TI2();
	S2BUF = value;
	while(TI2L);
	CLR_TI2();
	IE2 = IE2 | 0x01;
}*/
//=============================================================================
void UART3_PrintByte(u8 value)     //串口 3 发送单字节
{
	IE2 = IE2 & 0xF7;
	CLR_TI3();
	S3BUF = value;
	while(TI3L);
	CLR_TI3();
	IE2 = IE2 | 0x08;
} 
//=============================================================================
/*void UART4_PrintByte(u8 value)   //串口 4 发送单字节
{
	IE2 = IE2 & 0xEF;
	CLR_TI4();
	S4BUF = value;
	while(TI4L);
	CLR_TI4();
	IE2 = IE2 | 0x10;
} */


//=============================================================================
//设置volumeValue音量值从 0 到 8
void MP3_SetVolume(u8 volumeValue)	
{	
	if((volumeValue >= 0) && (volumeValue <= 30))
	{
		UART3_PrintByte(0x7E);
		UART3_PrintByte(0x04);
		UART3_PrintByte(0x31);
		UART3_PrintByte(volumeValue); //音量等级
		UART3_PrintByte((0x35^volumeValue)); //校验码
		UART3_PrintByte(0xEF);
	}		
}
//设置播放MP3文件
void MP3_SetPlay(unsigned char mulu, unsigned char wenjian)
{	
	u8 i=0x47;
	UART3_PrintByte(0x7E);		   //开始码
	UART3_PrintByte(0x05);		   //数据长度
	UART3_PrintByte(0x42);		   //功能码
	UART3_PrintByte(mulu);		   //文件夹的编号
	i = i ^ mulu;
	UART3_PrintByte(wenjian);		 //MP3文件的编号
	i = i ^ wenjian;
	UART3_PrintByte(i);
	UART3_PrintByte(0xEF);
}

//停止播放当前的音乐
void MP3_Stop(void)
{
	UART3_PrintByte(0x7E);
	UART3_PrintByte(0x03);
	UART3_PrintByte(0x1E);
	UART3_PrintByte(0x1D);
	UART3_PrintByte(0xEF);
}
//暂停当前播放的音乐
void MP3_Pause(void)
{	
	UART3_PrintByte(0x7E);
	UART3_PrintByte(0x03);
	UART3_PrintByte(0x12);
	UART3_PrintByte(0x11);
	UART3_PrintByte(0xEF);
}
//从暂停或停止当前音乐中恢复继续播发当前音乐
void MP3_RePlay(void)
{
	UART3_PrintByte(0x7E);
	UART3_PrintByte(0x03);
	UART3_PrintByte(0x11);
	UART3_PrintByte(0x12);
	UART3_PrintByte(0xEF);
}

#endif



















