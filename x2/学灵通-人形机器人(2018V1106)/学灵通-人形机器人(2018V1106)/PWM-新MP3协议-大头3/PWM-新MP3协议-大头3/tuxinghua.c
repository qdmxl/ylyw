//图形化子程序
#include <stdio.h>
#include <string.h>
#include"CH376INC.h"
#include "REG15W4Kxx.h"
#include "delay.h"

#include "main.h"
#include "basal.h"
#include "walking.h"
#include "qianshou.h"
#include "jiewu.h"
#include "ticao.h"
#include "qiaoxiyang.h"
//#include "adc.h"				//加速度传感器头文件

#include "SdCard.h"       //加入SD卡相关操作函数
#include "BUZZ.h"

int jichu[24];

extern unsigned int in;
extern unsigned int out;
extern u8 xdata RX1_Buffer[400];	     //接收缓冲
extern void UART1_PrintByte(u8 value); //串口1输出单个字节数据
extern void UART1_PrintArrayBytes(u8 *str, u16 len);

//#############################################################################
// 函数名称：uchar ReadRam()
// 函数说明：从存储区读数子程序
// 入口参数：无
// 出口参数：无
//#############################################################################
uchar ReadRam(void)
{
	uchar i;
  while(out == in);
   
	i = RX1_Buffer[out];
	++out;
	if(out == capacity)
		out = 0;

	/*if(in != out)
	{
		if(in > out)
		{
			if((400-in+out) < 50)
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
			if((out-in) < 50)  
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
	} */

  return i;
}
//#############################################################################
// 函数名称：void duoji(uchar num,uchar pos)
// 函数说明：单个舵机控制程序
// 入口参数：无
// 出口参数：无
//#############################################################################
void duoji(uchar num,uchar pos)
{  
    position_change[num]=pos-position[num];
		p_to_p(35,0);
}
//#############################################################################
// 函数名称：void main1(void)
// 函数说明：图形化编程模式
// 入口参数：无
// 出口参数：无
//#############################################################################
void main1(void)
{
	uint   keycode = 0;	   //按钮码缓冲变量
	uchar	 SrcName[12];	   //原文件名缓冲区	
	uint32 ByteCount;      //预存文件的大小
//	uchar  shuliang = 0;   //对存储按钮量的计数	
	uchar  i,j;
	bit OutFlag = 0;      //退出编辑动作模式
	
  while(1)
	{ 
		/*if(shuliang == 25)  //======== 检测25钮的存储
	  { 
			fm50ms(5); //蜂鸣器发声提示
			shuliang = 0;
			UART1_PrintByte(251); //25按钮存储完毕，返回251
	  } */
		if(ReadRam() == 253) //======= 前置码:253
		{
			i = ReadRam();
			switch(i)
			{
				case 1:								    //引导码1:每次存储32字节(舵机相关数据)
						keycode = ReadRam();	//按键码:从 0 到 65535   高位8在先
				    keycode = keycode << 8;
				    keycode = keycode | ReadRam();  //             低8位在后
						for(i=0;i<32;i++)
						{
							SdcardBuff[i] = ReadRam();																		 										
						}
						sprintf(SrcName, "/SHR1/%d", keycode);
						if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
							ByteCount = CH376ReadVar32(VAR_FILE_SIZE);
						else ByteCount = 0;
						if(ByteCount >= 32)
						{								
							i = WriteSdcardFileBuffBytes(SrcName, ByteCount);	
						}
						else i = WriteSdcardFileBuffBytes(SrcName, 0);
						//fm100ms(1);
						//UART1_PrintByte(251); //每存储完一个按键，回应一个251
					break;
				case 2:		//第二个引导码，2代表单个舵机运动
						i = ReadRam();
						j = ReadRam();
						duoji(i,j);
					break;						
				case 3:		//引导码3: 代表将初始位置存储
					 for(i=0;i<32;i++)						   
					 { 
						  if(i < 24)
								SdcardBuff[i] = ReadRam();
							else SdcardBuff[i] = 125;						  
           }
					 strcpy(SrcName, "/SHR0/0");  // 存储的源文件名	
					 if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
							i = WriteSdcardFileBuffBytes(SrcName, 0);	
					 fm200ms(1); //蜂鸣器提示
					 UART1_PrintByte(251);						
					break;						
				case 4:  //引导码4:上位机需要上传所有位置
					  /*keycode = ReadRam();	//按键码:从 0 到 24 
				    if(keycode < 200) //单个按键上传
						{
							sprintf(SrcName, "/SHR1/%d", keycode);
							if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
								ByteCount = CH376ReadVar32(VAR_FILE_SIZE);
							else ByteCount = 0;				
							UART1_PrintByte(253);
							UART1_PrintByte(253);
							UART1_PrintByte(253);
							UART1_PrintByte(253);
							UART1_PrintByte(1);
							UART1_PrintByte(keycode);
							if(ByteCount >= 32)
							{
								i = ReadSdcardFileAllBytes(SrcName);
							}
							delay10ms(2); 
							fm100ms(1); //蜂鸣器提示
					  }
            else */ 
            //{
						/*	for(keycode=0; keycode<25;keycode++)
							{ 
								sprintf(SrcName, "/SHR1/%d", keycode);
								if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
									ByteCount = CH376ReadVar32(VAR_FILE_SIZE);
								else ByteCount = 0;
								UART1_PrintByte(253);
								UART1_PrintByte(253);
								UART1_PrintByte(253);
								UART1_PrintByte(253);
								UART1_PrintByte(1);
								UART1_PrintByte(keycode);
								if(ByteCount >= 32)
								{
									i = ReadSdcardFileAllBytes(SrcName);
								}
								delay10ms(2);
								fm100ms(1); //蜂鸣器提示
							}		*/					
            //}	
						keycode = ReadRam();//键码
						keycode = keycode << 8;
						keycode = keycode | ReadRam();						
						sprintf(SrcName, "/SHR1/%d", keycode);
						if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
							ByteCount = CH376ReadVar32(VAR_FILE_SIZE);
						else ByteCount = 0;
						UART1_PrintByte(253);
						UART1_PrintByte(253);
						UART1_PrintByte(253);
						UART1_PrintByte(253);
						UART1_PrintByte(1);
						UART1_PrintByte(keycode>>8); //回传键码也是：高8位在先  低8位在后
						UART1_PrintByte(keycode);
						if(ByteCount >= 32)
						{
							i = ReadSdcardFileAllBytes(SrcName);
						}
						delay10ms(2);
						fm100ms(1); //蜂鸣器提示						
						UART1_PrintByte(251);
						delay500ms(2);
						UART1_PrintByte(251);
						delay500ms(2);
						UART1_PrintByte(251);
						delay500ms(2);
						UART1_PrintByte(251);						
					break;
				case 253:                 //引导码253: 代表即将结束			
						/*if(ReadRam() == 254)	//如果下一个数是254，则连续写入4个254至E2PROM，表示结束
						{
							if(shuliang == 0)   //首次要要下载时，创建文件 耗费时间大概7s
							{
								//UART1_PrintByte(252); //回传与上位机握手 两次252才结束
								/*for(j=0;j<25;j++)
								{
									keycode = j;
									sprintf(SrcName, "/SHR1/%d", keycode);
									CreateSdcardFile(SrcName);
								} */
								//UART1_PrintByte(252);
							/*}
							//fm100ms(1); //蜂鸣器发声提示
							shuliang++; 
					 } */
								
					 if(ReadRam() == 254) //第二个引导码，254代表即将结束
					 {
							 keycode = ReadRam();//键码
						   keycode = keycode << 8;
						   keycode = keycode | ReadRam();
							 fm100ms(1);//蜂鸣器发声提示 存储结束
					     UART1_PrintByte(252); //回传与上位机握手 两次252才结束
							 sprintf(SrcName, "/SHR1/%d", keycode);
							 CreateSdcardFile(SrcName);
						
							sprintf(SrcName, "/SHR0/%d", 2);
							if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
								ByteCount = CH376ReadVar32(VAR_FILE_SIZE);
							else ByteCount = 0;	
						
					     UART1_PrintByte(252); //回传与上位机握手 两次252才结束
					}
				 break;	
			 case 5:  //引导码5: 清除所有动作
					for(keycode=0;keycode<65535;keycode++)
					{
						sprintf(SrcName, "/SHR1/%d", keycode);
						CreateSdcardFile(SrcName);
						fm100ms(1);//蜂鸣器提示
					}	
					sprintf(SrcName, "/SHR1/%d", keycode);
					CreateSdcardFile(SrcName);
					//fm100ms(1);//蜂鸣器提示					
					fm100ms(4); //蜂鸣器提示	
					UART1_PrintByte(251);				 
				 break;
			 //case 6: //引导码6: 经典动作操作
			 //	 break;	
			 case 7:  //引导码7: 联机
					UART1_PrintByte(253);
				 break;
			 case 8:   //引导码8: 传绝对值
					for(i=0;i<24;i++)
					{
						position_change[i] = ReadRam() - position[i];
          }
					i = ReadRam();	
					p_to_p(40,i);	//参数：(55)延时、速度变化值	 
				 break;
				case 9:  //引导码9: 
						SdcardBuff[0] = ReadRam();     // part   第几台
						SdcardBuff[1] = ReadRam();     // total	 总台数		
				    SdcardBuff[10] = volume;
				    strcpy(SrcName, "/SHR0/1");  // 存储的源文件名
						if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
							i = WriteSdcardFileBuffBytes(SrcName, 0);
						UART1_PrintByte(251);
						fm100ms(2); //蜂鸣器提示
					break;
				case 11:  //回传有数据的键码
					/*for(keycode=0;keycode<40;keycode++)
					{
						sprintf(SrcName, "/SHR1/%d", keycode);								
						if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
						{
							ByteCount = CH376ReadVar32(VAR_FILE_SIZE);
							if(ByteCount >= 32)
							{
								UART1_PrintByte(keycode>>8); //先发H8
								UART1_PrintByte(keycode);    //后发L8
							}							
							//sprintf(TarName, "N%d:%d\r\n", keyNumber, ByteCount); 
							//UART1_PrintString(TarName);							
						}
						fm100ms(1);
						//i = CH376SendCmdDatWaitInt(CMD1H_FILE_CLOSE, TRUE);
					}
					sprintf(SrcName, "/SHR1/%d", keycode);								
					if(CH376FileOpenDir(SrcName, 0xFF) == USB_INT_SUCCESS)
					{
						ByteCount = CH376ReadVar32(VAR_FILE_SIZE);
						if(ByteCount >= 32)
						{
							UART1_PrintByte(0xFF);    //先发H8
							UART1_PrintByte(0xFF);    //后发L8
						}
						//sprintf(TarName, "N%d:%d\r\n", keyNumber, ByteCount); 
						//UART1_PrintString(TarName);							
					}	
					//i = CH376SendCmdDatWaitInt(CMD1H_FILE_CLOSE, TRUE);
					fm100ms(1); //蜂鸣器提示						
					UART1_PrintByte(251);
					fm100ms(1);
					UART1_PrintByte(251);
					fm100ms(1);
					UART1_PrintByte(251);
					fm100ms(1);
					UART1_PrintByte(251);			*/		
					break;
				case 10:  //置退出编辑动作模式标志
					OutFlag = 1;				  
					break;					
			}			
		}
		if(OutFlag == 1) //退出编辑动作模式
		{
			//fm300ms(2);
			break;
		}
	}

}
//#############################################################################
// 函数名称：void cyc(uchar time)
// 函数说明：图形化循环子程序
// 入口参数：循环次数（0-100）
// 出口参数：无
//#############################################################################
void cyc(PUINT32 Locate1, PUINT32 Locate2, uchar time)
{
	UINT16	ThisLen;
	UINT32	ByteCount;
	uchar   i, j, k, m;	
	int temp;
	
	while(time > 0) //----------->循环次数操作
	{
		ByteCount = *Locate1;//---->循环起点赋值
		do
		{
		   //sprintf(srcName, "/SHR1/%d", key); //取对应按键存储的动作数据组
		   //i = CH376FileOpenDir(srcName, 0xFF);	
			
				//取出一帧动作数据	
        i = CH376ByteLocate(ByteCount);			
				//if(CH376ByteLocate(ByteCount) != USB_INT_SUCCESS);  //以字节为单位移动当前文件指针到上次复制结束位置
				//	goto out;
			  i = CH376ByteRead(SdcardBuff, sizeof(SdcardBuff), &ThisLen);
				//if(CH376ByteRead(SdcardBuff, sizeof(SdcardBuff), &ThisLen) != USB_INT_SUCCESS)
				//	goto out;
			
				//取出动作数据处理  
				for(m=1;m<4;m++)		 				//判断24个舵机值的正负 SdcardBuff[1、2、3]
				{
					k = 0x80;
					for(i=0,j=0;i<8;i++)
					{
						if(m == 1) 
						{
							j = i;
							position_change[j] = SdcardBuff[i+4];	
						}
						else 
						{
							if(m == 2) 
							{
								j = i+8;
								position_change[j] = SdcardBuff[i+12];
							}						
							else 
							{
								j = i+16;
								position_change[j] = SdcardBuff[i+20];
							}
						}					
						if((SdcardBuff[m] & k) == k) //1-->逆时针转   变化量为负
						{	
							position_change[j] = 0 - position_change[j];
						}
						temp = position_change[j];
						position_change[j] = position_change[j] - jichu[j];
						jichu[j] = temp;
						//else	                    //0-->顺时针转   变化量为正
						k = k>>1;
					}
			 }

			 switch(SdcardBuff[30]) //取语音的第一个数据
			 { 
					case 251:
						if(SdcardBuff[31] == 251) //连续2个251  表示停止播放音乐
								MP3_Stop();
						break;
					case 252:
						if(SdcardBuff[31] == 252)	//连续2个101（0x65）表示音乐继续
							{;}
						break;
					default: 							//否则就为音乐曲目
						MP3_SetPlay(SdcardBuff[30], SdcardBuff[31]); //指定文件夹号与歌曲号  播放		
					break;
			}                     

			switch(SdcardBuff[28])			 //SdcardBuff[28]速度值>=200，则表示经典动作
			{    
				case 200:daoli();pch();break;//dt();
				case 201:turn_left(1);break;
				case 202:walk(2);break;
				case 203:turn_right(1);break;
				case 204:l_pyi(1);break;
				case 205:fwc(4);break;
				case 206:r_pyi(1);break;
				case 207:goal_l(1);break;
				case 208:yangwoqizuo(3);break;
				case 209:goal_r(1);break;
				case 210:jingli_l();break;
				case 211:jingli_r();break;
				case 212:qiaoxiyang();break;
				case 213:jiewu();break;
				case 214:qianshou();break;
				case 215:ticao();break;
				case 216:qgf();break;
				case 217:hgf();break;
				case 218:qianpaxia();qianpq();break;
				case 219:hp();hpq();break;	
				case 220:taijiaozi();break;
				case 221:houtui(2);break;
				case 222:;break;
				case 223:;break;
				case 224:;break;
				case 225:;break;
				case 226:;break;
				case 227:break;
				case 228:break;
				default: 	
				        p_to_p(SdcardBuff[28],SdcardBuff[28]);     	                
					break;			 
			}
		
			for(i=0; i<SdcardBuff[29]; i++)			   		 //提取延时时间  
			{ 
				delay10ms(10);
			}										  
		 
//			delay10us(5);
			
			//搞经典动作后处理
			if(SdcardBuff[28] >= 200)
			{
				for(i=0; i<24; i++)
				{
					jichu[i] = position[i] - position_initial[i];
				}			
			}
		
			ByteCount += ThisLen; //移动读取文件的指针			
			
		//UART1_PrintArrayBytes(SdcardBuff, ThisLen); //串口1输出显示+++++++++++++++++++
		//fm300ms(1);
		//delay1s(2);
			
		}while(ByteCount <= *Locate2);	   		
		time--;
	}
//out:return;  
}
//#############################################################################
// 函数名称：void location(uchar lo)
// 函数说明：运行模式中解析E2PROM子程序
// 入口参数：表示第lo个按键，去E2PROM执行相应的程序
// 出口参数：无
//#############################################################################	  
void location(u16	ThisLen) //传入按键号uint
{
	u8  i;
	u8  SrcName[12];	 //原文件名缓冲区	
	u32	FileSize, LoopLocate1, LoopLocate2, ByteCount;
	//int jichu[24];
	int temp;
	
	sprintf(SrcName, "/SHR1/%d", ThisLen); //取对应按键存储的动作数据组
	if(CH376FileOpenDir(SrcName, 0xFF) != USB_INT_SUCCESS) 	   //SD卡无动作文件	，播放无动作语音
	  {	
	    MP3_SetPlay(0x00, 113);	 
	  	return;
	  }
//	UART1_PrintByte(2);
	FileSize = CH376ReadVar32(VAR_FILE_SIZE);        //读取当前文件长度,判断是否有动作数据
	if(FileSize < 32)								 //此按键无动作，播放无动作语音
	{	
		MP3_SetPlay(0x00, 113);	            
		return;
	}
		   //有动作，播放开始表演音乐
		MP3_SetPlay(0x00, 111);	
		delay10ms(130);

//	UART1_PrintByte(3);
	
	ByteCount = 0;
	/*for(i=0;i<24;i++)
		jichu[i] = 0;*/
	i = 0; //用于记录循环起点标志
  do
  {
		  //sprintf(SrcName, "/SHR1/%d", key); //取对应按键存储的动作数据组
		  //SrcName[0] = CH376FileOpenDir(SrcName, 0xFF);
		
			//取出一帧动作数据		
		  SrcName[0] = CH376ByteLocate(ByteCount);
			//if(CH376ByteLocate(ByteCount) != USB_INT_SUCCESS); //以字节为单位移动当前文件指针到上次复制结束位置
			//	goto out;
		  SrcName[0] = CH376ByteRead(SdcardBuff, sizeof(SdcardBuff), &ThisLen);
			//if(CH376ByteRead(SdcardBuff, sizeof(SdcardBuff), &ThisLen) != USB_INT_SUCCESS)
			//	goto out;
		  
			//对取出的动作数据处理  
			for(SrcName[0]=1; SrcName[0]<4; SrcName[0]++)    //判断24个舵机值的正负 SdcardBuff[1、2、3]
			{
				SrcName[1] = 0x80;
				for(SrcName[2]=0,SrcName[3]=0; SrcName[2]<8; SrcName[2]++)
				{
					if(SrcName[0] == 1) 
					{
						SrcName[3] = SrcName[2];
						position_change[SrcName[3]] = SdcardBuff[SrcName[2]+4];	
					}
					else 
					{
						if(SrcName[0] == 2) 
						{
							SrcName[3] = SrcName[2]+8;
							position_change[SrcName[3]] = SdcardBuff[SrcName[2]+12];
						}						
						else 
						{
							SrcName[3] = SrcName[2]+16;
							position_change[SrcName[3]] = SdcardBuff[SrcName[2]+20];
						}
					}					
					if((SdcardBuff[SrcName[0]] & SrcName[1]) == SrcName[1]) //1-->逆时针转   变化量为负
					{	
						position_change[SrcName[3]] = 0 - position_change[SrcName[3]];				
					}
					temp = position_change[SrcName[3]];
					position_change[SrcName[3]] = position_change[SrcName[3]] - jichu[SrcName[3]];
					jichu[SrcName[3]] = temp; //记录上一次相对初始位置的变化量值
					//else	                    //0-->顺时针转   变化量为正
					SrcName[1] = SrcName[1]>>1;
				}
		 }
		 
		 switch(SdcardBuff[30]) //取语音的第一个数据
		 { 
					case 251:
						if(SdcardBuff[31] == 251) //连续2个251  表示停止播放音乐
								MP3_Stop();
						break;
					case 252:
						if(SdcardBuff[31] == 252)	//连续2个101（0x65）表示音乐继续
							{;}
						break;
					default: 							//否则就为音乐曲目
						MP3_SetPlay(SdcardBuff[30], SdcardBuff[31]); //指定文件夹号与歌曲号  播放		
					break;
		}                     

		switch(SdcardBuff[28])			 //SdcardBuff[28]速度值>=200，则表示经典动作
		{    
			case 200:daoli();pch();break;//dt();
			case 201:turn_left(1);break;
			case 202:walk(2);break;
			case 203:turn_right(1);break;
			case 204:l_pyi(1);break;
			case 205:fwc(4);break;
			case 206:r_pyi(1);break;
			case 207:goal_l(1);break;
			case 208:yangwoqizuo(3);break;
			case 209:goal_r(1);break;
			case 210:jingli_l();break;
			case 211:jingli_r();break;
			case 212:qiaoxiyang();break;
			case 213:jiewu();break;
			case 214:qianshou();break;
			case 215:ticao();break;
			case 216:qgf();break;
			case 217:hgf();break;
			case 218:qianpaxia();qianpq();break;
			case 219:hp();hpq();break;	
			case 220:taijiaozi();break;
			case 221:houtui(2);break;
			case 222:;break;
			case 223:;break;
			case 224:;break;
			case 225:;break;
			case 226:;break;
			case 227:break;
			case 228:break;
			default:           
				p_to_p(SdcardBuff[28],SdcardBuff[28]);      	                
				break;			 
		}
	
		for(SrcName[0]=0; SrcName[0]<SdcardBuff[29]; SrcName[0]++)			   		 //提取延时时间  
		{ 
			delay10ms(10);
		}										  
   
//		delay10us(5);

		if(SdcardBuff[0] > 128)
		{
			if(i == 0)  
			{
				LoopLocate1 = ByteCount;          //记下循环起点
				i = 1;
			}
		}
		else
		{
			if((SdcardBuff[0] > 0) && (SdcardBuff[0] < 128))
			{
				if(i == 1)
				{
					LoopLocate2 = ByteCount;  //记下循环结束点
					cyc(&LoopLocate1, &LoopLocate2, (SdcardBuff[0]-1));//执行循环部分
					i = 0;
				}
			}
		}
		
		//搞经典动作后处理
		if(SdcardBuff[28] >= 200)
		{
			for(SrcName[0]=0; SrcName[0]<24; SrcName[0]++)
			{
				jichu[SrcName[0]] = position[SrcName[0]] - position_initial[SrcName[0]];
			}			
    }
		
		ByteCount += ThisLen; //移动读取文件的指针		
		
		//UART1_PrintArrayBytes(SdcardBuff, ThisLen); //串口1输出显示+++++++++++++++++++
		//fm300ms(1);
		//delay1s(2);
		
  }while(ByteCount < FileSize);
	
	//s = CH376FileClose( TRUE );  //关闭文件,对于字节读写建议自动更新文件长度
	SrcName[0] = CH376SendCmdDatWaitInt(CMD1H_FILE_CLOSE, TRUE);
 
//out:delay10us(10);
}






