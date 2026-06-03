/*-------------------------------------------------------------------------------*/
/* ---------------- STC15 MCU 机器主板程序 --------------------------------------*/
/*-------------------------------------------------------------------------------*/
#include <setjmp.h>			
#include <stdio.h>
#include <intrins.h>
#include <string.h>
#include "REG15W4Kxx.h"
#include "USART.h"
#include "CH376DO.h"
#include "BUZZ.h"

#include "delay.h"
#include "tuxinghua.h"

#include "adc.h"
//#include "INFRARED.h"
#include "HT1621.h"

#include "basal.h"			//基础动作
#include "walking.h"

#include "jiewu.h"
#include "ticao.h"
#include "qianshou.h"
#include "qiaoxiyang.h"

#include "PSX.h"
//#include "PSX2.h"

jmp_buf envbuf;

unsigned char volume = 8;       //音量值的大小

bit acc_bit = 0;
bit flag_acc_enable = 0;	      //加速计传感器允许标志位
unsigned char flag_power = 0;		//加速度传感器标志位

unsigned char anjian = 0;		    //按键标志位
unsigned char zhuangtai = 0;	  //按键标志位

//===============================================================
//芯片初始化
void CPU_Init(void) 
{ 
  u8 i;

	CLK_DIV = 0x01;
//	delay10ms(10);
	//P6 = 0x00;
	//P7 = 0x00;
	//P2 = 0x00;
	//PWM_Init(); //初始化硬PWM
	//所有I/O口全设为准双向，弱上拉模式	   	注:若使用硬PWM则设置PWM输出口为强推挽模式
	P0M0 = 0x00;	 //P0.6->PWM7_2  P0.7->PWM6_2
	P0M1 = 0x00;
	P1M0 = 0x00;
	P1M1 = 0x00;
	P2M0 = 0x00;   //P2.7->PWM2_2   
	P2M1 = 0x00;	  
	P3M0 = 0x00;
	P3M1 = 0x00;
	P4M0 = 0x20;   //P4.5->PWM3_2	 P4.4->PWM4_2  P4.2->PWM5_2
	P4M1 = 0x00;
	P5M0 = 0x10;
	P5M1 = 0x00;
	P6M0 = 0x00;
	P6M1 = 0x00;
	P7M0 = 0x00;
	P7M1 = 0x00;
	
	Uart_Init();   //初始化串口部分
  
	//init_inf();   //初始化红外部分	
	Inf_Init();     //新有遥控器解码
	
	t0_init();     //PWM脉宽最大时间控制
	
	Init_SPI();    //手柄SPI接口配置 -->硬件SPI操作
//	SPI_init();    //模拟SPI操作
	
	EA = 1;

	//while(mInitCH376Host() != 0x51);//命令操作: 0x51-->成功  0x5F-->失败
	while(mInitCH376Host() != 0x51){MP3_SetPlay(0x00,63);fm100ms(5);delay500ms(1);delay10ms(2);}//命令操作: 0x51-->成功  0x5F-->失败

	in = 0;
	out = 0;
	
	for(i=0;i<24;i++)
		jichu[i] = 0;	
}

//===============================================================
void Accel_Init(void)  //加速计初始检测
{
  P40 = 1;
	if(P40 != 1)
	{
		//flag_acc_enable = 1;  //标志ACC插上了
		delay500us(50);
		initial_adc();        //初始化ADC采样部分
		delay500us(50);		
		get_balance_value();	//获取平衡角度
	}	
}

//===============================================================
//链接PC机上的编辑动作软件检测
bit DoCheckout_Online(void)
{
	unsigned char ii = 0, jj = 0; //联机命令																		            
	for(ii=0;ii<10;)					     //如果连续收到10个“S”说明上位机要求联机
	{
		if(ReadRam() != 0x53)       //如果等于0，说明没有收到“S”
		{ 
			delay10ms(3);				           //延时30ms
			jj++;
			if(jj > 80)				             //如果0个30ms都没有收到“S”->0x53
				return 0;
				//goto xy;				           //跳到图形化的运行模式
		}		  
		else
    	{			
			//if(RX1_Buffer[ii] == 0x53)
			//{											 
				ii++;
			//}
		}
		//fm1ms(1);
	}
	return 1;
}

//===============================================================
//发送所有舵机的初始位置
void UART1Send_InitPositon(void)
{ 
	unsigned char i = 0;
	for(i=0; i<24; i++)
	{
		UART1_PrintByte(SdcardBuff[i]); //暂时调试用
		delay10ms(5); //延时50ms
	}
}

//===============================================================
//链接PC机上的编辑动作软件初始化处理
void Online_DoInit(void)
{ 
	u8 xdata SrcName[10];			// 原文件名缓冲区
	UART1_PrintByte(0xFC);		//联机成功后等待3s，必须等
	delay1s(1);
	UART1_PrintByte(0xFE);	  //发送初始位置前置码
	delay1s(1);	
	strcpy(SrcName, "/SHR0/0");  // 源文件名
	if(ReadSdcardFile32Bytes(SrcName) == USB_INT_SUCCESS)
	{
		UART1Send_InitPositon();    //发送初始位置值
	}        
}
//===============================================================
//链接PC机上的编辑动作软件初始化处理
void QianShou_DoInit(void)
{ 
	u8 xdata SrcName[10];			   // 原文件名缓冲区
	strcpy(SrcName, "/SHR0/1");  // 源文件名
	if(ReadSdcardFile32Bytes(SrcName) == USB_INT_SUCCESS)
	{
		change = 16;
		part   = SdcardBuff[0];
		total  = SdcardBuff[1];
		volume = SdcardBuff[10];//取得音量值
	}        
}
//===============================================================
//存取特殊参数
void SetValueParas(void)
{
	u8 i;
	u8 xdata SrcName[10];			   // 原文件名缓冲区
	SdcardBuff[0] = part;        // part   第几台
	SdcardBuff[1] = total;       // total	 总台数		
	SdcardBuff[10] = volume;
	strcpy(SrcName, "/SHR0/1");  // 存储的源文件名
	if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
		i = WriteSdcardFileBuffBytes(SrcName, 0);	
}
//===============================================================
//24路舵机输出子程序，实现24路舵机的PWM信号在最短的时间内输出
void PWM_24(void)
{      
		uchar i,j;
		for(i=0;i<=7;i++)          //取P6口舵机对应的值
		{arr[i]=position[i];}
		array();                   //排序计算   
		low_level_t0(0x9400);		   //定时器赋初始值,22.1184MHz,2.5Ms定时ee00

		P6=0xff;                   //使口P6全部拉高
		delay500us(1);             //调用延时500us函数
		for(i=0;i<8;i++)           //P6口8路同时输出
		{      
			for(j=0;j<arr[7-i];j++)  
			{delay8us(1);}
			P6=P6&pick_up[7-i];
		} 
		while(t0bit==0);	

///////////////////////////////////////////////////////////	   		 
		for(i=0;i<8;i++)           //给排序数组赋值
		{arr[i]=position[i+8];}
		array();                   //调用排序子程序
		low_level_t0(0x9400);		   //定时器赋初始值,22.1184MHz,2.5Ms定时ee00	 				

		P7=0xff;                   //使口P7全部拉高
		delay500us(1);             //调用延时500us函数
		for(i=0;i<8;i++)           //P7口8路同时输出
		{        
			for(j=0;j<arr[7-i];j++)  
			{delay8us(1);}
			P7=P7&pick_up[7-i];
		}
		while(t0bit==0);
	
//////////////////////////////////////////////////////////		      
		for(i=0;i<8;i++)                   //给排序数组赋值
		{arr[i]=position[i+16];}
		array();                   //调用排序子程序
		P2=0xFF;                //使口P2全部拉高  从P20-P25
		low_level_t0(0x9400);		   //定时器赋初始值,22.1184MHz,2.5Ms定时ee00	   				

		delay500us(1);             //调用延时500us函数
		for(i=0;i<8;i++)           //P2口6路同时输出
		{   
			for(j=0;j<arr[7-i];j++)  
			{delay8us(1);}
			P2=P2&pick_up[7-i];						  
		}	
		while(t0bit==0);		
		TR0 = 0;	 

//////////////////////////////////////////////////////////	   
	 if(flag_acc_enable==1)
	 {
	   if(flag_adjust==1)
	   {
	     adc_adjust();
		   if(flag_jump==1)
		   {
		       longjmp(envbuf,1); 
		   }
	   }
	 }
 
}

/********************* 主函数***********************************/
void main(void)
{      
	u16 i,j,k;   
	u8 n=0;						 //定义红外遥控器按键位数标志位
	
	CPU_Init();                  //CPU初始化处理	 
	fm100ms(3);					         //初始化第一次提示
	QianShou_DoInit();           //牵手观音相关处理
	initial_position();	  		   //初始位置 
	Accel_Init();                //加速计上电检测	
	MP3_SetVolume(volume);       //上电设置MP3播放模块的音量大小	
  	fm200ms(1);                  //初始化第二次提示,标识结束
	MP3_SetPlay(0x00,60);	 //欢迎语
	setjmp(envbuf);              //设置返回jumb点
	flag_jump = 0;
	
	RX1_mode = 0; //目前调试使用
	in = 0;
	out = 0;
	EX0  = 1;
	B_IR_Press = 0;		//清除IR键按下标志
		
	while(1)
	{ 
		
//=============== 串口1处理部分 ===========================================
		if(out != in) //在线联机处理
		{
			EX0 = 0;
			TR1 = 0;
			if(DoCheckout_Online() == 1)
			{
				Online_DoInit();                 //链接成功处理
				MP3_SetPlay(0x00,0x3D);     //播放语音提示，进入三维编辑模式
				delay1s(3);
				main1();   				         //进入图形化调试模式	
       	   	    MP3_SetPlay(0x00,0x3E);	 //播放语音提示，退出三维编辑模式			
			}
			EX0 = 1;
			B_IR_Press = 0;		//清除IR键按下标志	
			n=0;		
		}	
//=============== 串口2处理部分 ===========================================		
		if(RX2_flag == 1)   //-------------------------串口2控制部分
		{	
			EX0 = 0;
      		TR1 = 0;			
			switch(RX2_Key)
			{
				case 100:       // 准备状态----------------->0
					Start_Status(0, 16);
				  anjian = 0;
					break;
				case 101:       // 前进状态----------------->1
					if(anjian == 1)
					{
					  MP3_SetPlay(0x05,1);
					  kuaizou2(); }	
					else
						kuaizou1();
					anjian = 1;					
					break;
				case 102:      // 后退状态----------------->2
					if(anjian == 1)
						{MP3_SetPlay(0x05,3);
						  houtui2();  } 
					else
						houtui1();
					anjian = 1;					
					break;	
				case 103:      // 左转状态----------------->3
					anjian = 0;
					MP3_SetPlay(0x05,2);
                    turn_left(1); 										
					break;
				case 104:      // 右转状态----------------->4
					anjian = 0;
					MP3_SetPlay(0x05,2);
					turn_right(1);				
					break;
				case 105:      // 前滚翻状态--------------->5
					anjian = 0;
					MP3_SetPlay(0x05,5);
					qgf();		
					break;
				case 106:      // 后滚翻状态--------------->6
					anjian = 0; 
					MP3_SetPlay(0x05,7);
					hgf();				
					break;	
				case 107:      // 左平移状态--------------->7
					anjian = 0;
					MP3_SetPlay(0x05,6);
					l_pyi(1);				
					break;
				case 108:      // 右平移状态--------------->8
					anjian = 0;	
					MP3_SetPlay(0x05,6);
					r_pyi(1);	
					break;
				case 109:      // 左勾球--------------->9
					  MP3_SetPlay(0x05,15);
					  zuogouqiu(); //左勾球						
					break;
				case 110:      // 右勾求--------------->10  
					  MP3_SetPlay(0x05,15);
					  yougouqiu(); //右勾球					
					break;
				case 111:      // 左踢----------------------->11
					  MP3_SetPlay(0x05,10);
					  goal_l(1);				
					break;
				case 112:      // 右踢 ------------>12
					  MP3_SetPlay(0x05,10);
					  goal_r(1);					
					break;

				case 120:      //  --------------
					   P55 = 1;
						if(P55 == 1)
							fm100ms(5);
						else
						 {						
							flag_power = !flag_power;
							if(flag_power == 0)
							 {
								flag_acc_enable = 0;
								fm100ms(1);			//响一声,关闭三轴加速计
							 }
							else
							 {
								flag_acc_enable = 1;
								fm100ms(2);	   //响两声,开启三轴加速计
							 }
						 }					
					break;

				case 121: //+音量加键（VOL）
					if(volume < 30)
					{
						volume++;
						MP3_SetVolume(volume);
						SetValueParas();
					}
					MP3_SetPlay(0x00,0x41);
					break;		
				case 122: //-音量减键（VOL）
					if(volume > 1)
					{
						volume--;
						MP3_SetVolume(volume);
						SetValueParas();				
					}
					MP3_SetPlay(0x00,0x41);
					break;
					
				default: //从 0 到 99 分别对应：从 0 到 99 的location ----> 20 -- 44
					if((RX2_Buffer[0] >= 0)&&(RX2_Buffer[0] <= 99))
					{
					         relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	     					 p_to_p(10,10);

   							if( RX2_Buffer[0] < 10)	           
							 { 
						      MP3_SetPlay(0x00,	(0x64+RX2_Buffer[0]) );
							  delay10ms(75);			
							  location(RX2_Buffer[0]);     //执行相应类型的动作
							  break;
							 }
							else
							 {
							  MP3_SetPlay(0x00, (0x64+((RX2_Buffer[0]-(RX2_Buffer[0]%10))/10))  );
							  delay10ms(75);
							  MP3_SetPlay(0x00, (0x64+	(RX2_Buffer[0]%10)	)  );
							  delay10ms(75);			
							  location(RX2_Buffer[0]);     //执行相应类型的动作
							  break;
							 }
      				}
					break;
			}
			
			EX0 = 1;
			B_IR_Press = 0;		//清除IR键按下标志
      		RX2_flag = 0;	
			n=0;		
		}
		
//================ 加速计处理部分 ===========================================		
		if(flag_acc_enable == 1)
		{
			adc_adjust();			
		}
			delay100us(85);
		
//================ 手柄处理部分 ===========================================		
		Obtain_PSXCode();
		PSXKey_Filter();
		if(psx_key != 0xFF)
		{
			EX0 = 0;
      		TR1 = 0;			
			psx_key_buff_flag = 0;
			psx_key_buff = 0xFF;//UART1_PrintByte(psx_key);
			if(psx_mode_flag == 0)
			 {
				switch(psx_key)
				{
					case 0:       // SELECT + START 键组合										
						break;
					case 1:					    //前进按键 1 
						if(anjian == 1)
						 {  MP3_SetPlay(0x05,1);
							kuaizou2();}
						else
							kuaizou1();
							anjian = 1;					
						break;
					case 2:					   //向右转按键 2 											
							MP3_SetPlay(0x05,2);
							anjian = 0;
							turn_right(1);
						break;
					case 3:				      //后退按键 3 											
						   if(anjian == 1)
							{   MP3_SetPlay(0x05,3);
								houtui2();	}
						   else
							  houtui1();
							  anjian = 1;
						break;
					case 4:				      //向左转按键 4 					
						    MP3_SetPlay(0x05,2);
							anjian = 0;
							turn_left(1);
						break;
					case 5:				     //前滚翻按键 5 								
						  	MP3_SetPlay(0x05,5);
							anjian = 0;
							qgf(); //前滚翻  
						break;
					case 6:				     //向右平移按键 6 							
							MP3_SetPlay(0x05,6);
							anjian = 0;
							r_pyi(1);					
						break;
					case 7:				     //后滚翻按键 7	
							MP3_SetPlay(0x05,7);
							anjian = 0;
							hgf();	//后滚翻  
						break;
					case 8:			        //向左平移按键 8 							
						    MP3_SetPlay(0x05,6);
							anjian = 0;
							l_pyi(1);
						break;
					case 9:  break;			   //1 -- 5  组合键
					case 10: break; 	      //1 -- 6	 组合键
					case 11: break; 		  //1 -- 7	 组合键
					case 12: break; 		  //1 -- 8	 组合键
					case 13: break;  		  //2 -- 5  组合键
					case 14: break; 		  //2 -- 6	组合键
					case 15: break; 		  //2 -- 7	 组合键
					case 16: break; 		  //2 -- 8	 组合键
					case 17: break; 	     //3 -- 5 	组合键
					case 18: break;		 	//3 -- 6	组合键
					case 19: break; 		 //3 -- 7	组合键
					case 20: break; 		 //3 -- 8	组合键	     
					case 21: break; 		 //4 -- 5 	组合键
					case 22: break; 		 //4 -- 6	组合键
					case 23: break; 		 //4 -- 7	组合键
					case 24: break; 		 //4 -- 8	组合键
					case 25: break;	       //按 R1、L1、R2、L2  组合键
					case 26: break;	       //按 R1、L1、R2
					case 27: break;	       //按 R1、L1、L2
					case 28: 			   //按 R1、L1
						  if(volume < 30)
							{
								volume++;
								MP3_SetVolume(volume);
								SetValueParas();
							}
							MP3_SetPlay(0x00,0x41);
						break;	       
					case 29: break;	       //按 R1、R2、L2 
					case 30: break;	       //按 R1、R2
					case 31: break;	       //按 R1、L2
					case 32: 			   //按 R1 键
						  MP3_SetPlay(0x05,15);
						  yougouqiu(); //右勾球
						break;	       
					case 33: break;	       //按 L1、R2、L2
					case 34: break;	       //按 L1、R2
					case 35: break;	       //按 L1、L2
					case 36:		       //按 L1 键
						  MP3_SetPlay(0x05,15);
						  zuogouqiu(); //左勾球
						break;	 
					case 37: 			//按 R2、L2
						  if(volume > 1)
							{
								volume--;
								MP3_SetVolume(volume);
								SetValueParas();				
							}
							MP3_SetPlay(0x00,0x41);
						break;	 
					case 38: 		      //按 R2 键
						  MP3_SetPlay(0x05,10);
						  goal_r(1);				
						  anjian=0;
						break;	 
					case 39:			  //按 L2 键
						  MP3_SetPlay(0x05,10);
						  goal_l(1);				
						  anjian=0;
						break;	 
			
					case 40:	             //*** SELECT 键 ***					
						P55 = 1;
						if(P55 == 1)
							fm100ms(5);
						else
						 {						
							flag_power = !flag_power;
							if(flag_power == 0)
							 {
								flag_acc_enable = 0;
								fm100ms(1);			//响一声,关闭三轴加速计
							 }
							else
							 {
								flag_acc_enable = 1;
								fm100ms(2);	   //响两声,开启三轴加速计
							 }
						 } 	
						break;
					case 41:                 //*** START 键  ***
						fm100ms(1);
						MP3_SetPlay(0x05,20);
						initial_position_slowOne(3); //回到初始位置	
						anjian = 0;
						break;
					case 42:	             //*** Mode 键 ****
						fm100ms(1);          
						psx_mode_flag = !psx_mode_flag; //切花模式标志
						break; 																							
				   }				
			 }
			else
			 {
				switch(psx_key)
				{
					case 51:  //左边摇杆
						if(anjian == 1)
						{
							MP3_SetPlay(0x05,1);
							kuaizou2(); }	//前进
						else
							kuaizou1();
						    anjian = 1;
						break;      
					case 52: 
						anjian = 0;
						MP3_SetPlay(0x05,2);
						turn_right(1); //右转
						break;   
					case 53: 
						if(anjian == 1)
							{MP3_SetPlay(0x05,3);
							  houtui2();	} //后退
						else
							houtui1();
						    anjian = 1;
						break;  
					case 54: 
						anjian = 0;
						MP3_SetPlay(0x05,2);
						turn_left(1); //左转
						break;       
					case 55:  //右边摇杆
						anjian = 0;
						MP3_SetPlay(0x05,5);
						qgf();       //前滚翻					
						break;    
					case 56:
						anjian = 0;	
						MP3_SetPlay(0x05,6);
						r_pyi(1);	 //右平移						 
						break;  
					case 57:
						anjian = 0; 
						MP3_SetPlay(0x05,7);
						hgf();      //后滚翻					
						break;       
					case 58:
						anjian = 0;
						MP3_SetPlay(0x05,6);
						l_pyi(1);	//左平移			 
						break;
					case 40:       //*** SELECT 键 ***
						P55 = 1;
						if(P55 == 1)
							fm100ms(5);
						else
						{						
							flag_power = !flag_power;
							if(flag_power == 0)
							{
								flag_acc_enable = 0;
								fm100ms(1);			//响一声,关闭三轴加速计
							}
							else
							{
								flag_acc_enable = 1;
								fm100ms(2);	   //响两声,开启三轴加速计
							}
						}					 								
						break;
					case 41:       //*** START 键 ***
						fm100ms(1);
						MP3_SetPlay(0x05,20);
						initial_position_slowOne(3); //回归初始位置
						anjian = 0;
						break;	
					case 42:	   //*** MODE 键 ***		
						fm100ms(1);          
						psx_mode_flag = !psx_mode_flag; //切花模式标志
						break;
					case 43: break;				 //左边摇杆按钮 
					case 44: break;				 //右边摇杆按钮
					case 45: break;  			 //左边+右边摇杆按钮
					default:
					   if(psx_key < 25)	           //前25个键从 0 到 24
						{	 
							 relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	     					 p_to_p(10,10);

						    if(psx_key < 10)	           
							 { 
						      MP3_SetPlay(0x00, (0x64+psx_key) );
							  delay10ms(75);			
							  location(psx_key);     //执行相应类型的动作
							  break;
							 }
							else
							 {
							  MP3_SetPlay(0x00, (0x64+((psx_key-(psx_key%10))/10))  );
							  delay10ms(75);
							  MP3_SetPlay(0x00, (0x64+(psx_key%10))  );
							  delay10ms(75);			
							  location(psx_key);     //执行相应类型的动作
							  break;
							 }
						}
					   else
						{
							switch(psx_key)
							   {
								case 25: break;	 //按下 R1、L1、R2、L2  组合键
								case 26: break;	 //按下 R1、L1、R2
								case 27: break;	 //按下 R1、L1、L2
								case 28: 			   //按 R1、L1
									  if(volume < 30)
										{
											volume++;
											MP3_SetVolume(volume);
											SetValueParas();
										}
										MP3_SetPlay(0x00,0x41);
									break;	       
								case 29: break;	       //按 R1、R2、L2 
								case 30: break;	       //按 R1、R2
								case 31: break;	       //按 R1、L2
								case 32: 			   //按 R1 键
									  MP3_SetPlay(0x05,15);
									  yougouqiu(); //右勾球
									break;	       
								case 33: break;	       //按 L1、R2、L2
								case 34: break;	       //按 L1、R2
								case 35: break;	       //按 L1、L2
								case 36:		       //按 L1 键
									  MP3_SetPlay(0x05,15);
									  zuogouqiu(); //左勾球
									break;	 
								case 37: 			//按 R2、L2
									  if(volume > 1)
										{
											volume--;
											MP3_SetVolume(volume);
											SetValueParas();				
										}
										MP3_SetPlay(0x00,0x41);
									break;	 
								case 38: 		      //按 R2 键
									  MP3_SetPlay(0x05,10);
									  goal_r(1);				
									  anjian=0;
									break;	 
								case 39:			  //按 L2 键
									  MP3_SetPlay(0x05,10);
									  goal_l(1);				
									  anjian=0;
									break;						
							   }
						}									
						break;				
				}				
          }
 
			Clear_PSXBuff();
			EX0 = 1;	
      		B_IR_Press = 0;		//清除IR键按下标志
			n=0;			
		}
		else
		{
			if(anjian_bit == 1)
			{	
				EX0 = 0;
      		  	TR1 = 0;			
				anjian = 0;	
				anjian_bit = 0;
				Start_Status(0, 16);  
				EX0 = 1;
			}			
		}
		
		
//================ 红外处理部分 ===========================================
		if(B_IR_Press == 1)		//有IR键按下
		{
			EX0 = 0;
			TR1 = 0;
			switch(IR_code)
			{
				case 0x46: //启停姿态传感器开关
					  //UART1_PrintByte(0x46);
						n=0;
						P55 = 1;
						if(P55 == 1)
							fm100ms(5);
						else
						{						
							flag_power = !flag_power;
							if(flag_power == 0)
							{
								flag_acc_enable = 0;
								fm100ms(1);			//响一声,关闭三轴加速计
							}
							else
							{
								flag_acc_enable = 1;
								fm100ms(2);	   //响两声,开启三轴加速计
							}
						}	
					break;
				case 0x0C: //A键
				          n=0;
						  MP3_SetPlay(0x00,52);
					      jiewu();
					break;
				case 0x08: //B键
						  n=0;
						  MP3_SetPlay(0x00,53);
				          ticao();
					break;
				case 0x04: //C键
						  n=0;
						  MP3_SetPlay(0x00,54);
				          qianshou();
					break;	
				case 0x00: //D键
						  n=0;
						  MP3_SetPlay(0x00,51);
				          qiaoxiyang();
					break;
				
				case 0x0D: //E键
						  n=0;
						  MP3_SetPlay(0x00,18);
						  dt_l();
					break;
				case 0x09: //F键
						  n=0;
						  MP3_SetPlay(0x00,19);
						  dt_r();
					break;
				case 0x05: //G键
						  n=0;
						  MP3_SetPlay(0x00,20);
						  zuogouqiu();
					break;
				case 0x01: //H键
						  n=0;
						  MP3_SetPlay(0x00,21);
						  yougouqiu();
					break;
				
				case 0x0E: //I键 
						  n=0;
						  wudao();
					break;
				case 0x0A: //J键
						  n=0;
					break;
				case 0x06: //K键
						  n=0;
					break;	
				case 0x02: //L键
						  n=0;
					break;
				
				case 0x0F: //M键
						  n=0;
					break;
				case 0x0B: //N键
						  n=0;
					break;
				case 0x07: //O键
						  n=0;
					break;	
				case 0x03: //P键
						  n=0;
					break;
				
				case 0x4C: //Q键
						  n=0;
				          MP3_SetPlay(0x00,14);
				          qgf();       //前滚翻
					break;
				case 0x48: //R键
						  n=0;
				          MP3_SetPlay(0x00,12);
				          qianpaxia();
						  qianpq();
					break;
				case 0x44: //S键
						  n=0;
						  MP3_SetPlay(0x00,5);
				          fwc(4);
					break;
				case 0x40: //T键
						  n=0;
						  MP3_SetPlay(0x00,16); 
						  daoli();
					break;

				case 0x4D: //U键
						  n=0;
						  MP3_SetPlay(0x00,15);
				          hgf();
					break;
				case 0x49: //V键
						  n=0;
						  MP3_SetPlay(0x00,13);
				          hp();
						  hpq();
					break;
				case 0x45: //W键
						  n=0;
						  MP3_SetPlay(0x00,8);
				          yangwoqizuo(4);
					break;		
				case 0x41: //X键
						  n=0;
						  MP3_SetPlay(0x00,17);
						  pch();
					break;

				case 0x4E: //>||播放键
						  n=0;
					break;
				case 0x4F: //.暂停键
						  n=0;
					break;
				case 0x42: //+音量加键（VOL）
					if(volume < 30)
					{
						volume++;
						MP3_SetVolume(volume);
						SetValueParas();
					}
					MP3_SetPlay(0x00,0x41);
					break;		
				case 0x43: //-音量减键（VOL）
					if(volume > 1)
					{
						volume--;
						MP3_SetVolume(volume);
						SetValueParas();				
					}
					MP3_SetPlay(0x00,0x41);
					break;	
				
				case 0x18: //左转键
						  n=0;
						  MP3_SetPlay(0x00,1);
				          turn_left(1);
						  relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	    				  p_to_p(10,20);
					break;
				case 0x10: //右转键
						  n=0;
						  MP3_SetPlay(0x00,3);
				          turn_right(1);
						  relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	    				  p_to_p(10,20);
					break;	
				case 0x14: //向上键
						  n=0;
						  MP3_SetPlay(0x00,2);
				          walk(5);
					break;
				case 0x15: //ENTER键
						  n=0;
				          relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	    				  p_to_p(10,30);
					break;
				case 0x16: //向下键
						  n=0;
				          houtui(4);
					break;
				case 0x19: //向左键
						  n=0;
						  MP3_SetPlay(0x00,4);
				          l_pyi(1);
						  relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	    				  p_to_p(10,20);
					break;
				case 0x11: //向右键
						  n=0;
						  MP3_SetPlay(0x00,6);
				          r_pyi(1);
						  relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	    				  p_to_p(10,20);
					break;	

				case 0x1A: //左踢脚键
						  n=0;
						  MP3_SetPlay(0x00,7);
				          goal_l(1);
						  relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	    				  p_to_p(10,20);
					break;
				case 0x12: //右踢脚键
						  n=0;
						  MP3_SetPlay(0x00,9);
				          goal_r(1);
						  relative(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);
	    				  p_to_p(10,20);
					break;				
				
				case 0x1F: // 1 键
				          n++;
						       if(n==1){i=1;MP3_SetPlay(0x00,0x65);}
						  else if(n==2){j=1;MP3_SetPlay(0x00,0x65);}
						  else if(n==3){k=1;MP3_SetPlay(0x00,0x65);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;
				case 0x1B: // 2 键
				          n++;
						       if(n==1){i=2;MP3_SetPlay(0x00,0x66);}
						  else if(n==2){j=2;MP3_SetPlay(0x00,0x66);}
						  else if(n==3){k=2;MP3_SetPlay(0x00,0x66);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;
				case 0x17: // 3 键
				          n++;
						       if(n==1){i=3;MP3_SetPlay(0x00,0x67);}
						  else if(n==2){j=3;MP3_SetPlay(0x00,0x67);}
						  else if(n==3){k=3;MP3_SetPlay(0x00,0x67);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;

				case 0x5C: // 4 键
				          n++;
						       if(n==1){i=4;MP3_SetPlay(0x00,0x68);}
						  else if(n==2){j=4;MP3_SetPlay(0x00,0x68);}
						  else if(n==3){k=4;MP3_SetPlay(0x00,0x68);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;
				case 0x58: // 5 键
				          n++;
						       if(n==1){i=5;MP3_SetPlay(0x00,0x69);}
						  else if(n==2){j=5;MP3_SetPlay(0x00,0x69);}
						  else if(n==3){k=5;MP3_SetPlay(0x00,0x69);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;
				case 0x54: // 6 键
				          n++;
						       if(n==1){i=6;MP3_SetPlay(0x00,0x6A);}
						  else if(n==2){j=6;MP3_SetPlay(0x00,0x6A);}
						  else if(n==3){k=6;MP3_SetPlay(0x00,0x6A);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;
				
				case 0x5D: // 7 键
				          n++;
						       if(n==1){i=7;MP3_SetPlay(0x00,0x6B);}
						  else if(n==2){j=7;MP3_SetPlay(0x00,0x6B);}
						  else if(n==3){k=7;MP3_SetPlay(0x00,0x6B);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;
				case 0x59: // 8 键
				          n++;
						       if(n==1){i=8;MP3_SetPlay(0x00,0x6C);}
						  else if(n==2){j=8;MP3_SetPlay(0x00,0x6C);}
						  else if(n==3){k=8;MP3_SetPlay(0x00,0x6C);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;
				case 0x55: // 9 键
				          n++;
						       if(n==1){i=9;MP3_SetPlay(0x00,0x6D);}
						  else if(n==2){j=9;MP3_SetPlay(0x00,0x6D);}
						  else if(n==3){k=9;MP3_SetPlay(0x00,0x6D);}
						  else   {MP3_SetPlay(0x00,0x70);}   
					break;
				case 0x50: // 0 键
				          n++;
						       if(n==1){i=0;MP3_SetPlay(0x00,0x64);}
						  else if(n==2){j=0;MP3_SetPlay(0x00,0x64);}
						  else if(n==3){k=0;MP3_SetPlay(0x00,0x64);}
						  else   {MP3_SetPlay(0x00,0x70);}
					break;

				case 0x13: //取消键
						  n=0;    MP3_SetPlay(0x00,0x6E);
					break;

				case 0x51: // OK 键
				               if(n==0){ MP3_SetPlay(0x00,0x70); }
						  else if(n==1){ location(i);  }
						  else if(n==2){ location((i*10)+j);	 }
						  else if(n==3){ location((i*100)+(j*10)+k);	}
						  else		   { MP3_SetPlay(0x00,0x70); }
						     n=0;	    	   	
						             
					break;	
			}
			EX0  = 1;
			B_IR_Press = 0;		//清除IR键按下标志
		} 
		
	}

}

/********************* UART1中断函数************************/
void UART1_Interrupt(void) interrupt UART1_VECTOR
{
	if(RI)
	{
		RI = 0;
		RX1_Buffer[in] = SBUF;		
		/*if(RX1_mode == 1)
		{			
			//SBUF = RX1_Buffer[0]; //------->调式时使用
			RX1_flag = 1;
			in = 0;
			return;
		} */
		
		++in;
		if(in == capacity)		   	
			in = 0;
		/*if(in > out)
		{
			if((400 - in + out) < 50)
			{
				BUSY=1;
				ES=0;
			}
			else
			{
				BUSY=0;
				ES=1;
			}
		}
		else
		{
			if((out - in) < 50)  
			{
				BUSY=1;
				ES=0;
			}
			else 
			{
				BUSY=0;
				ES=1;
			}
		}		*/	
	}
	else TI = 0;
}

/********************* UART2中断函数************************/
void UART2_Interrupt(void) interrupt UART2_VECTOR
{
	if(RI2) //协议: 0xFF 0xFF 0x01 LEN PARA PARA SUM
	{
		CLR_RI2();
		RX2_Buffer[RX2_in] = S2BUF;
//		S2BUF = RX2_Buffer[0]; //------->调式时使用
		if(RX2_in < 2)
		{
			if(RX2_Buffer[RX2_in] == 0xFF)
				RX2_in++;
			else RX2_in = 0;
			RX2_Buffer[15] = 0;//SUM
		}
		else
		{
			if(RX2_in < 4)
			{
				RX2_Buffer[15] = RX2_Buffer[15] + RX2_Buffer[RX2_in];
				RX2_in++;
				if(RX2_in == 4)
					RX2_Buffer[14] = RX2_Buffer[3] + 4;
			}
			else
			{
				if(RX2_in < RX2_Buffer[14])
				{
					RX2_Buffer[15] = RX2_Buffer[15] + RX2_Buffer[RX2_in];
					RX2_in++;
				}
				else
				{
					if(RX2_Buffer[15] == RX2_Buffer[RX2_in])
					{
						if(RX2_Buffer[2] == 0x01)
						{
							RX2_Key = RX2_Buffer[4];
							RX2_Key = RX2_Key << 8;
							RX2_Key = RX2_Key | RX2_Buffer[5];
						}					
						RX2_flag = 1;
          }
					RX2_in = 0;
        }
			}
		}
		//RX2_flag = 1;
	}
	else CLR_TI2();
}

/********************* UART3中断函数************************/
void UART3_Interrupt(void) interrupt UART3_VECTOR
{
	if(RI3)
	{
		CLR_RI3();
		RX3_Buffer[0] = S3BUF;
//		S3BUF = RX3_Buffer[0]; //------->调式时使用
		
	}
	else CLR_TI3();
}

/********************* UART4中断函数************************/
void UART4_Interrupt(void) interrupt UART4_VECTOR
{
	if(RI4)
	{
		CLR_RI4();
		RX4_Buffer[0] = S4BUF;
//		S4BUF = RX4_Buffer[0];  //-------->调式时使用
		RX4_flag = 1;
	}
	else CLR_TI4();
}






//===============================================================================
//===============================================================================
//===============================================================================






























		//buf[0] = RX4_Buffer[29];
		//adc_averageValue = buf[0];
		//sprintf(buf, "/SHR1/%d", adc_averageValue);
		//UART1_PrintString(buf);

/*
  fm100ms(1);                   //进入动作执行模式提示
	//MP3_SetPlay(0x00,0x00,61);	  //播报对应的语音提示 -------->注意声音文件
	//delay1s(2);
	
	if(Checkout_Online() == 1)    //链接上位机软件检测
	{
		Online_DoInit();            //链接成功处理
		MP3_SetPlay(0x00,0x00,63);  //播放语音提示  ------------->注意声音文件
		delay1s(3);
		main1();   				          //进入图形化调试模式
	} 
	
	
//链接PC机上的编辑动作软件检测
bit Checkout_Online(void)
{
	unsigned char ii = 0, jj = 0; //联机命令																		            
	for(ii=0;ii<10;)					     //如果连续收到10个“S”说明上位机要求联机
	{
		if(RX1_Buffer[ii] != 0x53)       //如果等于0，说明没有收到“S”
		{ 
			delay10ms(3);				           //延时30ms
			jj++;
			if(jj > 80)				             //如果0个30ms都没有收到“S”->0x53
				return 0;
				//goto xy;				           //跳到图形化的运行模式
		}		  
		else
    {			
			//if(RX1_Buffer[ii] == 0x53)
			//{
				ii++;
			//}
		}
	}
	return 1;
}

	u8  s;
	u8	xdata	SrcName[32];				//原文件名缓冲区
	u8	xdata	TarName[32];				//目标文件名缓冲区
	u16 keyNumber = 0;
	u16 ByteCount;
	
		if(RX1_flag == 1)
		{
			RX1_flag = 0; //读取文件
			if(RX1_Buffer[0] < 25)  
			{
				keyNumber = RX1_Buffer[0];
				//strcpy(SrcName, "/SHR1/1");  // 源文件名
				sprintf(SrcName, "/SHR1/%d", keyNumber);
				//s = CH376FileOpenPath(SrcName);   //打开文件,该文件在C51子目录下
				s = CH376FileOpenDir(SrcName, 0xFF);	
				if((s != ERR_MISS_DIR) && (s != ERR_MISS_FILE)) 						
					s = ReadSdcardFileAllBytes(SrcName); //输出显示						
			}
			else
			{
				switch(RX1_Buffer[0])
				{
					case 255: //创建25个文件
							SBUF = 0x00;
							for(s=0;s<25;s++)
							{
								keyNumber = s;
								sprintf(SrcName, "/SHR1/%d", keyNumber);
								CreateSdcardFile(SrcName);
							}
							SBUF = 0x11;						
						break;
					case 254: //读取25个文件的大小
						  for(s=0;s<25;s++)
							{
								keyNumber = s;
								sprintf(SrcName, "/SHR1/%d", keyNumber);								
								if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
								{
									ByteCount = CH376ReadVar32(VAR_FILE_SIZE);
									sprintf(TarName, "N%d:%d\r\n", keyNumber, ByteCount); 
									UART1_PrintString(TarName);
								}
						  }
						break;
					case 253: //获取初始位置
						strcpy(SrcName, "/SHR0/0");  // 源文件名
					  if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
						{
							s = ReadSdcardFileAllBytes(SrcName);
            }
						break;	
					case 252: //获取机器序号、总台数
						strcpy(SrcName, "/SHR0/1");  // 源文件名
					  if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
						{
							s = ReadSdcardFileAllBytes(SrcName);
            }				
						break;					
				}					
			}
			
		}
*/
