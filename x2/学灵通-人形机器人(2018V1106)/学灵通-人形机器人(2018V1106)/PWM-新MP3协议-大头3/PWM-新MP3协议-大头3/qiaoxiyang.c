#include "REG15W4Kxx.h"  				//芯片头文件
#include "delay.h"
#include "main.h"
#include "basal.h"
#include "qianshou.h"
#include "jiewu.h"

//#############################################################################
// 函数名称：void  xiyang_1()
// 函数说明：俏夕阳抖
// 入口参数：无
// 出口参数：无
//#############################################################################		 
void xiyang_1(void)
{
/*         uchar j,i;
		      for(j=0;j<50;j++)                         
			    {
			     position[6]-=1;
				 position[7]+=1;
				 PWM_24();
               	 low_level_500u(40);
				}
		      for(j=0;j<20;j++)                         
			    {
			     position[13]+=4;
				 position[14]+=4;
				 position[16]-=3;
				 PWM_24();	
				 low_level_500u(50);
				}
		  for(i=0;i<5;i++)                         
			{
			  for(j=0;j<6;j++)                         
			    {
			     position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
					 PWM_24();
				 low_level_500u(75);
				}
			  for(j=0;j<6;j++)                         
			    {
			     position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
					 PWM_24();
				 low_level_500u(75);
				}
		    }
			     delay10ms(20);
			     ForwardDelay();
				 ForwardDelay();
				 ForwardDelay();
				 ForwardDelay();
				 ForwardDelay();
				 ForwardDelay();
				 ForwardDelay();
			  
			  for(j=0;j<20;j++)                         
			    {
			     position[12]-=4;
				 position[13]-=4;
				 position[14]-=4;
				 position[15]-=4;
				 position[16]+=6;
					 PWM_24();
				 low_level_500u(50);
				}
		  for(i=0;i<5;i++)                         
			{
			  for(j=0;j<6;j++)                         
			    {
			     position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
					 PWM_24();
				 low_level_500u(75);
				}
			  for(j=0;j<6;j++)                         
			    {
			     position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
					 PWM_24();
				 low_level_500u(75);
				}
		    }
			       BackDelay();
				   BackDelay();
				   BackDelay();
				   BackDelay();
				   BackDelay();
				   BackDelay();
				   BackDelay();
				   
				   delay10ms(20);
		  for(i=0;i<2;i++)                         
			{
			  for(j=0;j<20;j++)                         
			    {
			     position[12]+=4;
				 position[13]+=4;
				 position[14]+=4;
				 position[15]+=4;
				 position[16]-=6;
					 PWM_24();
				 low_level_500u(40);
				}
			  for(j=0;j<20;j++)                         
			    {
			     position[12]-=4;
				 position[13]-=4;
				 position[14]-=4;
				 position[15]-=4;
				 position[16]+=6;
					 PWM_24();
				 low_level_500u(40);
				}
				    delay10ms(20);
					delay10ms(20);
			}
		  for(i=0;i<3;i++)                         
			{
			  for(j=0;j<20;j++)                         
			    {
			     position[12]+=4;
				 position[13]+=4;
				 position[14]+=4;
				 position[15]+=4;
				 position[16]-=6;
					 PWM_24();
				 low_level_500u(40);
				}
			  for(j=0;j<20;j++)                         
			    {
			     position[12]-=4;
				 position[13]-=4;
				 position[14]-=4;
				 position[15]-=4;
				 position[16]+=6;
					 PWM_24();
				 low_level_500u(40);
				}
				    
			}
			  for(j=0;j<20;j++)                         
			    {
			     position[12]+=4;
				 position[15]+=4;
				 position[16]-=3;
					 PWM_24();
				 low_level_500u(40);
				}
			  for(j=0;j<10;j++)                         
			    {
			     position[6]+=5;
				 position[7]-=5;
					 PWM_24();
				 low_level_500u(40);
				}
              	  delay500ms(1);
				  initial_position(); */
}
//#############################################################################
// 函数名称：void  qiaoxiyang_2()
// 函数说明：俏夕阳直角肩
// 入口参数：无
// 出口参数：无
//#############################################################################	
void xiyang_2(void)
{
/*          
             uchar j,i;
		      for(j=0;j<18;j++)                         
			    {
			     position[12]-=5;
				 position[14]+=5;
					
				  PWM_24();
               	 low_level_500u(40);
				}
		  
		      for(j=0;j<11;j++)                         
			    {
			     position[12]-=3;
				 position[13]+=6;
				 position[14]-=3;
				 position[15]+=6;
					 PWM_24();
             	 low_level_500u(25);
				}
				  delay500ms(1);
		  for(i=0;i<2;i++)                         
			{
			  for(j=0;j<22;j++)                         
			    {
			     position[12]+=3;
				 position[13]-=6;
				 position[14]+=3;
				 position[15]-=6;
					PWM_24();
				 low_level_500u(25);
				}
				   delay10ms(1);
				   delay10ms(1);
			  for(j=0;j<22;j++)                         
			    {
			     position[12]-=3;
				 position[13]+=6;
				 position[14]-=3;
				 position[15]+=6;
					PWM_24();
				 low_level_500u(25);
				}
				   delay500ms(1);
			}
		  for(i=0;i<2;i++)                         
			{
			  for(j=0;j<22;j++)                         
			    {
			     position[12]+=3;
				 position[13]-=6;
				 position[14]+=3;
				 position[15]-=6;
				 	PWM_24();				
				 low_level_500u(25);
				}
				   delay10ms(1);
				   delay10ms(1);
			  for(j=0;j<22;j++)                         
			    {
			     position[12]-=3;
				 position[13]+=6;
				 position[14]-=3;
				 position[15]+=6;
					 PWM_24();
				 low_level_500u(25);
				}
				   delay10ms(1);
				   delay10ms(1);
			}
			  for(j=0;j<22;j++)                         
			    {
			     position[12]+=3;
				 position[13]-=6;
				 position[14]+=3;
				 position[15]-=6;
					 PWM_24();
				 low_level_500u(25);
				}
				   delay10ms(1);
				   delay10ms(1);
			  for(j=0;j<11;j++)                         
			    {
			     position[12]-=3;
				 position[13]+=6;
				 position[14]-=3;
				 position[15]+=6;
					 PWM_24();
				 low_level_500u(25);
				}
				 delay10ms(20);
			  for(j=0;j<10;j++)                         
			    {
			 	 position[6]-=9;
				 position[7]+=9;
				 	 PWM_24();
				 low_level_500u(75);
				}
				   delay500ms(1);

	      for(i=0;i<2;i++)                         
		    {
			  for(j=0;j<10;j++)                         
			    {
			 	 position[12]+=10;
				 position[13]+=5;
				 position[14]-=10;
				 position[15]-=5;
				 	 PWM_24();
                  low_level_500u(70);
				}
				  delay10ms(1);
			  for(j=0;j<10;j++)                         
			    {
			 	 position[12]-=10;
				 position[13]-=5;
				 position[14]+=10;
				 position[15]+=5;
			       PWM_24();
                  low_level_500u(70);
				}
				    delay10ms(20);
			}
			  for(j=0;j<30;j++)                         
			    {
			 	 position[0]-=3;
				 position[2]-=1;
				 position[3]+=3;
				 position[5]+=1;
				 position[12]+=3;
				 position[14]-=3;
					delay1ms(5);
					 PWM_24();
                  low_level_500u(70);
				  
				}
				   delay500ms(1);

		  for(i=0;i<2;i++)                         
			{
			  for(j=0;j<20;j++)                         
			    {
			     position[13]+=4;
				 position[14]+=4;
				 position[16]-=5;
					 PWM_24();
				 low_level_500u(35);
				}
			  for(j=0;j<20;j++)                         
			    {
			     position[13]-=4;
				 position[14]-=4;
				 position[16]+=5;
					 PWM_24();
				 low_level_500u(35);
				}
				    delay10ms(20);
			}

		  for(i=0;i<2;i++)                         
			{
			  for(j=0;j<20;j++)                         
			    {
			     position[12]-=4;
				 position[15]-=4;
				 position[16]+=5;
					 PWM_24();
				 low_level_500u(35);
				}
			  for(j=0;j<20;j++)                         
			    {
			     position[12]+=4;
				 position[15]+=4;
				 position[16]-=5;
					 PWM_24();
				 low_level_500u(35);
				}
				    delay10ms(20);
			}
			  for(j=0;j<20;j++)                         
			    {
			     position[12]-=4;
				 position[15]-=4;
				 position[16]+=5;
					 PWM_24();
				 low_level_500u(35);
				}
		 for(i=0;i<3;i++)                         
		   {
		      for(j=0;j<20;j++)                         
			    {
			     position[12]+=4;
				 position[15]+=4;
				 position[16]-=5;
					 PWM_24();
				 low_level_500u(35);
				}
			  for(j=0;j<20;j++)                         
			    {
			     position[13]+=4;
				 position[14]+=4;
				 position[16]-=5;
					 PWM_24();
				 low_level_500u(35);
				}
				  
			  for(j=0;j<20;j++)                         
			    {
			     position[13]-=4;
				 position[14]-=4;
				 position[16]+=5;
					 PWM_24();
				 low_level_500u(35);
				}
			  for(j=0;j<20;j++)                         
			    {
			     position[12]-=4;
				 position[15]-=4;
				 position[16]+=5;
					 PWM_24();
				 low_level_500u(35);
				}
				  
           }
		      for(j=0;j<20;j++)                         
			    {
			     position[12]+=4;
				 position[15]+=4;
				 position[16]-=5;
					 PWM_24();
				 low_level_500u(35);
				}
				   delay10ms(20);
			  for(j=0;j<30;j++)                         
			    {
			 	 position[0]+=3;
				 position[2]+=1;
				 position[3]-=3;
				 position[5]-=1;
				 position[6]+=3;
				 position[7]-=3;
					delay10ms(1);
					 PWM_24();
                  low_level_500u(70);
				  
				}
				   delay500ms(1);
			   initial_position();  */
}
//#############################################################################
// 函数名称：void  qiaoxiyang_3()
// 函数说明：俏夕阳右踢腿
// 入口参数：无
// 出口参数：无
//#############################################################################	
void xiyang_3(void)
{ 
/*             uchar j,i;
		      for(j=0;j<20;j++)                         
			    {
			 	 position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
					 PWM_24();
				 low_level_500u(60);
				}
				   delay500ms(1);
		  for(i=0;i<2;i++)                         
		    {
			  for(j=0;j<20;j++)                         
			    {
			 	 position[3]+=2;
				 position[4]-=4;
				 position[5]-=2;
				 position[6]-=4;
					 PWM_24();
				 low_level_500u(40);
				}
				  delay10ms(1);
			  for(j=0;j<20;j++)                         
			    {
			 	 position[3]-=2;
				 position[4]+=4;
				 position[5]+=2;
				 position[6]+=4;
					 PWM_24();
				 low_level_500u(40);
				}
				  delay500ms(1);
		    }
		  for(i=0;i<3;i++)                         
		    {
			  for(j=0;j<20;j++)                         
			    {
			 	 position[3]+=2;
				 position[4]-=4;
				 position[5]-=2;
				 position[6]-=4;
					 PWM_24();
				 low_level_500u(40);
				}
			  for(j=0;j<20;j++)                         
			    {
			 	 position[3]-=2;
				 position[4]+=4;
				 position[5]+=2;
				 position[6]+=4;
					 PWM_24();
				 low_level_500u(40);
				}
			}
			     delay10ms(1);
			  for(j=0;j<20;j++)                         
			    {
			 	 position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
					 PWM_24();
				 low_level_500u(60);
				}
				 delay500ms(1);
				 initial_position();   */
}
//#############################################################################
// 函数名称：void  qiaoxiyang_4()
// 函数说明：俏夕阳摆手
// 入口参数：无
// 出口参数：无
//#############################################################################	
void xiyang_4(void)
{ 
/*     uchar j,i;
	 uint m,i1,i2;
	 i1=part;
	 i2=total;
		 m=180/(i2-1);
		for(i=1;i<=(part-1);i++)                           
		    {
		    relative(0,0,0,0,0,0,0,0,0,0,0,0,(-1)*i*m,0,i*m,0,0,0,0,0,0,0);
	        p_to_p(15,15);
			delay500ms(1);
			}
		 
		  for(i=0;i<(total-part);i++)                           
		    {
			  for(j=0;j<11;j++)                           
			    {
			     position[12]-=0;
				 position[14]+=0;
				  PWM_24();
				 low_level_500u(25);
			    }
				  delay500ms(1);
		    }	
			  m=180/(i2-1);
			  for(j=0;j<(total-1);j++)                           
			    {
				if(j>=part)
			       position[12]-=m;  			//若循环次数大于台数，则左肩抬起来。
			    else
				   position[12]-=0;			    //否则左肩不动
				
				if(part>total-j)
				   position[14]-=m;			//若台数大于总数减循环次数，则右肩放下
				else
				   position[14]-=0;
				    PWM_24();					//否则右肩不动
				 low_level_500u(25);
				 delay500ms(1);
			 
			    } 
				
			  delay500ms(1);
			   ForwardDelay();
			  for(j=0;j<77;j++)                         
			    {
			 	 position[12]+=2;
				 position[14]+=2;
					 PWM_24();
				 low_level_500u(60);
				}	
				 BackDelay();
			 /* for(j=0;j<5;j++)                         
			    {
			 	 position[12]-=18;
				 position[14]-=13;
					 PWM_24();
				 low_level_500u(75);
				}  */
				
/*		    relative(0,0,0,0,0,0,0,0,0,0,0,0,-88,0,88,0,0,0,0,0,0,0);
	        p_to_p(15,15);
			
		   for(i=0;i<2;i++)                         
		     {
			  for(j=0;j<20;j++)                         
			    {
			 	 position[9]-=1;
				 position[11]+=1;
				 position[12]-=4;
				 position[13]-=4;
				 position[14]+=4;
				 position[15]+=4;
					 PWM_24();
				 low_level_500u(60);
				}
				  delay10ms(1);
			  for(j=0;j<20;j++)                         
			    {
			 	 position[9]+=1;
				 position[11]-=1;
				 position[12]+=4;
				 position[13]+=4;
				 position[14]-=4;
				 position[15]-=4;
					 PWM_24();
				 low_level_500u(60);
				}
				   delay10ms(20);
		     }
		
			      delay10ms(20);
			  for(j=0;j<50;j++)                         
			    {
			     position[6]-=1;
				 position[7]+=1;
					 PWM_24();
				 low_level_500u(30);
				}
				 UART1_PrintByte(0x99);
	 
        if ((part%2)==1)
		 {

			  for(j=0;j<20;j++)                         
			    {
			     position[12]+=4;
				 position[13]+=4;
				 position[16]-=3;
					 PWM_24();
				 low_level_500u(50);
				}
		  for(i=0;i<5;i++)                         
			{
			  for(j=0;j<8;j++)                         
			    {
			     position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
					 PWM_24();
				 low_level_500u(75);
				}
			  for(j=0;j<8;j++)                         
			    {
			     position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
					 PWM_24();
				 low_level_500u(75);
				}
		    }
			  for(j=0;j<20;j++)                         
			    {
			     position[12]-=4;
				 position[13]-=4;
				 position[14]-=4;
				 position[15]-=4;
				 position[16]+=6;
					 PWM_24();
				 low_level_500u(50);
				}
		  for(i=0;i<5;i++)                         
			{
			  for(j=0;j<8;j++)                         
			    {
			     position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
					 PWM_24();
				 low_level_500u(75);
				}
			  for(j=0;j<8;j++)                         
			    {
			     position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
					 PWM_24();
				 low_level_500u(75);
				}
		    }
			  for(j=0;j<10;j++)                         
			    {
			     position[12]+=9;
				 position[14]-=1;
				 position[15]+=8;
				 position[16]-=6;
					 PWM_24();
				 low_level_500u(70);
				}
		}

	   else
		{
		      for(j=0;j<20;j++)                         
			    {
			     position[14]-=4;
				 position[15]-=4;
				 position[16]+=3;
					 PWM_24();
				 low_level_500u(50);
				}
		  for(i=0;i<5;i++)                         
			{
			  for(j=0;j<8;j++)                         
			    {
			     position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
					 PWM_24();
				 low_level_500u(75);
				}
			  for(j=0;j<8;j++)                         
			    {
			     position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
					 PWM_24();
				 low_level_500u(75);
				}
		    }
			  for(j=0;j<20;j++)                         
			    {
			     position[12]+=4;
				 position[13]+=4;
				 position[14]+=4;
				 position[15]+=4;
				 position[16]-=6;
					 PWM_24();
				 low_level_500u(50);
				}
		  for(i=0;i<5;i++)                         
			{
			  for(j=0;j<8;j++)                         
			    {
			     position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
					 PWM_24();
				 low_level_500u(75);
				}
			  for(j=0;j<8;j++)                         
			    {
			     position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
					 PWM_24();
				 low_level_500u(75);
				}
		    }
			  for(j=0;j<10;j++)                         
			    {
				 position[12]+=1;
			     position[13]-=8;
				 position[14]-=9;
				 position[16]+=6;
					 PWM_24();
				 low_level_500u(70);
				}
		}
		      for(j=0;j<50;j++)                         
			    {
			     position[6]+=1;
				 position[7]-=1;
					 PWM_24();
				 low_level_500u(30);
				}
			  
		 	   delay500ms(1); 
			   initial_position();  */
}
//#############################################################################
// 函数名称：void  qiaoxiyang_5()
// 函数说明：俏夕阳佐踢腿
// 入口参数：无
// 出口参数：无
//#############################################################################	

void xiyang_5(void)
{ 
             uchar j,i;
			  for(j=0;j<20;j++)                         
			    {
			 	 position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
					 PWM_24();
				 low_level_500u(60);
				}
				   delay10ms(20);
				   ForwardDelay();
				    ForwardDelay();
					 ForwardDelay();
					 ForwardDelay();
				    ForwardDelay();
					 ForwardDelay();
					 ForwardDelay();
					 ForwardDelay();
		  for(i=0;i<2;i++)                         
		    {
			  for(j=0;j<20;j++)                         
			    {
			 	 position[0]-=2;
				 position[1]+=4;
				 position[2]+=2;
				 position[7]+=4;
					 PWM_24();
				 low_level_500u(40);
				}
				  delay10ms(1);
			  for(j=0;j<20;j++)                         
			    {
			 	 position[0]+=2;
				 position[1]-=4;
				 position[2]-=2;
				 position[7]-=4;
					 PWM_24();
				 low_level_500u(40);
				}
				  delay500ms(1);
		    }
			     BackDelay();
				 BackDelay();
				 BackDelay();
				 BackDelay();
				 BackDelay();
				 BackDelay();
				 BackDelay();
				 BackDelay();
		  for(i=0;i<3;i++)                         
		    {
			  for(j=0;j<20;j++)                         
			    {
			 	 position[0]-=2;
				 position[1]+=4;
				 position[2]+=2;
				 position[7]+=4;
					 PWM_24();
				 low_level_500u(40);
				}
			  for(j=0;j<20;j++)                         
			    {
			 	 position[0]+=2;
				 position[1]-=4;
				 position[2]-=2;
				 position[7]-=4;
					 PWM_24();
				 low_level_500u(40);
				}
			}
			     delay10ms(1);
			  for(j=0;j<20;j++)                         
			    {
			 	 position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
					 PWM_24();
				 low_level_500u(60);
				}
				delay500ms(1);
				initial_position(); 
}
//#############################################################################
// 函数名称：void qiaoxiyang_6()
// 函数说明：俏夕阳上下手
// 入口参数：无
// 出口参数：无
//#############################################################################	

void xiyang_6(void)
{ 
             uchar j,i,k,l;
			  for(j=0;j<30;j++)                         
			    {
			 	 position[12]-=3;
				 position[14]+=3;
				 	 PWM_24();
				 low_level_500u(40);
				}
		   	  for(j=0;j<25;j++)                         
			    {
			 	 position[13]-=4;
				 position[15]-=4;
				 	 PWM_24();
				 low_level_500u(40);
				}
				   delay10ms(20);
		  for(i=0;i<2;i++)                         
		    {
			  for(j=0;j<8;j++)                         
			    {
			 	 position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
				 position[12]-=7;
				 position[13]+=7;
				 position[14]-=7;
				 position[15]+=7;
				 position[16]+=5;
				 	 PWM_24();
				 low_level_500u(70);
				}
				   delay10ms(1);
			  for(j=0;j<8;j++)                         
			    {
			 	 position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
				 position[12]+=7;
				 position[13]-=7;
				 position[14]+=7;
				 position[15]-=7;
				 position[16]-=5;
				 	 PWM_24();
				 low_level_500u(70);
				}
				delay500ms(1);
	        }
			  for(j=0;j<50;j++)                         
			    {
			 	 position[13]+=4;
				 position[15]+=4;
				 	 PWM_24();
				 low_level_500u(40);
				}
		  for(i=0;i<2;i++)                         
		    {
			  for(j=0;j<8;j++)                         
			    {
			 	 position[8]+=1;
				 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
				 position[12]+=7;
				 position[13]-=7;
				 position[14]+=7;
				 position[15]-=7;
				 position[16]-=5;
				 	 PWM_24();
				 low_level_500u(70);
				}
				   delay10ms(1);
			  for(j=0;j<8;j++)                         
			    {
			 	 position[8]-=1;
				 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
				 position[12]-=7;
				 position[13]+=7;
				 position[14]-=7;
				 position[15]+=7;
				 position[16]+=5;
				 	 PWM_24();
				 low_level_500u(70);
				}
				delay500ms(1);
	        }
			  for(j=0;j<10;j++)                         
			    {
			 	 position[7]+=19;
			 	 position[13]-=10;
				 position[15]-=10;
				 	 PWM_24();
				 low_level_500u(70);
				}
				  delay500ms(1);
			    k=4;
		  for(i=0;i<4;i++)                         
			{  
			  for(j=0;j<8;j++)                         
			    {
			 	 position[8]+=1;
			 	 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
			 	 position[12]+=k;
				 position[14]-=k;
				 	 PWM_24();
				 low_level_500u(70);
				}
				 delay10ms(1);
			  for(j=0;j<8;j++)                         
			    {
			 	 position[8]-=1;
			 	 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
			 	 position[12]-=k;
				 position[14]+=k;
				 	 PWM_24();
				 low_level_500u(70);
				}
				delay10ms(20);
			     	k=k+2;
			}
			  for(j=0;j<10;j++)                         
			    {
			 	 position[6]-=19;
				 position[7]-=19;
			 	 	 PWM_24();
				 low_level_500u(70);
				}
				  delay10ms(20);
		 	    l=4;
		  for(i=0;i<4;i++)                         
			{  
			  for(j=0;j<8;j++)                         
			    {
			 	 position[8]-=1;
			 	 position[9]+=1;
				 position[10]-=1;
				 position[11]+=1;
			 	 position[12]+=l;
				 position[14]-=l;
				 position[16]+=5;
				 	 PWM_24();
				 low_level_500u(70);
				}
				 delay10ms(1);
			  for(j=0;j<8;j++)                         
			    {
			 	 position[8]+=1;
			 	 position[9]-=1;
				 position[10]+=1;
				 position[11]-=1;
			 	 position[12]-=l;
				 position[14]+=l;
				 position[16]-=5;
				 	 PWM_24();
				 low_level_500u(70);
				}
				delay10ms(20);	 
			     	l=l+2;
			}
			  for(j=0;j<10;j++)                         
			    {
			 	 position[7]+=19;
				 	 PWM_24();
				 low_level_500u(70);
				}
				  delay10ms(20);
		  for(i=0;i<3;i++)                         
		    {
			  for(j=0;j<10;j++)                         
			    {
			 	 position[12]+=10;
				 position[13]+=5;
				 position[14]-=10;
				 position[15]-=5;
				      PWM_24();
                  low_level_500u(70);
				}
				  delay10ms(1);
			  for(j=0;j<10;j++)                         
			    {
			 	 position[12]-=10;
				 position[13]-=5;
				 position[14]+=10;
				 position[15]+=5;
				       PWM_24();
                  low_level_500u(70);
				}
				    delay10ms(20);
			}
			  for(j=0;j<10;j++)                         
			    {
			 	 position[6]+=19;
				 position[7]-=19;
				 	 PWM_24();
				 low_level_500u(70);
				}
				delay10ms(20);
			  for(j=0;j<30;j++)                         
			    {
			 	 position[12]+=3;
				 position[14]-=3;
				 	 PWM_24();
				 low_level_500u(70);
				}
			    	delay500ms(1); 
					initial_position();
			       
}
//#############################################################################
// 函数名称：void qiaoxiyang_xiao7()
// 函数说明：俏夕阳前夕阳
// 入口参数：无
// 出口参数：无
//#############################################################################	

void xiyang_xiao7(uchar sudu1)
{
              uchar i;

          for(i=0;i<50;i++)
		    {  
		       position[6]-=4;             
			   position[7]+=4;              
			          PWM_24();
			         low_level_500u(sudu1);
		      	
            }
		  for(i=0;i<50;i++)
		    {  
			   position[6]+=4;             
			   position[7]-=4;              
			    PWM_24();
		        low_level_500u(sudu1);
            }
         
		    
}
//#############################################################################
// 函数名称：void qiaoxiyang_7()
// 函数说明：俏夕阳前夕阳
// 入口参数：无
// 出口参数：无
//#############################################################################	

void xiyang_7(void)
{
              uchar k,i,j;
             for(i=0;i<15;i++)
		       {   
			    position[12]--;            
			    position[14]++;       
				 PWM_24();      
			      low_level_500u(50);
               }
       for(k=0;k<3;k++)
         {
	         for(i=0;i<10;i++)
		       {
                position[8]--;           
			    position[9]--;           
                position[10]--;         
			    position[11]--;          
                position[12]++;            			    
                position[14]++;       
				 PWM_24();    
			    low_level_500u(70);
			   }
	         for(i=0;i<20;i++)
		       {
			    position[8]++;           
			    position[9]++;            

                position[10]++;          
			    position[11]++;         

                position[12]--;           
			    
                position[14]--;       
				 PWM_24();    
                 low_level_500u(70);
			   }
	         for(i=0;i<10;i++)
		       {
			    position[8]--;            
			    position[9]--;            
                position[10]--;          
			    position[11]--;          
                position[12]++;            			    
                position[14]++;       
				 PWM_24();     
			     low_level_500u(70);
			   }
	  }
           for(i=0;i<15;i++)
		      {  
			   position[12]++;             
			   position[14]--;        
			    PWM_24();     
			   low_level_500u(50);
              }

		  for(i=0;i<95;i++)
		    {  
			   position[12]--;
		       position[14]++;
   			    PWM_24();
		       low_level_500u(25);
            }

			  xiyang_xiao7(50);
			  xiyang_xiao7(40);
			  xiyang_xiao7(30);
			    delay10ms(20);
	 for(j=0;j<2;j++)
	   {
		if((part%2)==1)
		  {

			for(i=0;i<8;i++)
		      {
               position[8]-=1;              
			   position[9]+=1;             
			   position[10]-=1;            
			   position[11]+=1;       
			    PWM_24();     
                low_level_500u(40);
		       }		
			     delay10ms(1);
			for(i=0;i<20;i++)
		      {
               position[0]-=3;              
			   position[1]+=6;
			   position[2]+=3;             
			   position[10]-=2;            
			   position[11]+=2;       
			    PWM_24();     
                low_level_500u(70);
		
		      }
			     delay500ms(1);
			for(i=0;i<20;i++)
		      {
               position[0]+=3;              
			   position[1]-=6;
			   position[2]-=3;             
			   position[10]+=2;            
			   position[11]-=2;       
			    PWM_24();     
                low_level_500u(70);
		       }
			     delay10ms(1);
			for(i=0;i<8;i++)
		      {
               position[8]+=1;              
			   position[9]-=1;             
			   position[10]+=1;            
			   position[11]-=1;       
			    PWM_24();     
                low_level_500u(40);
		       }
			     
		  }
		
		else

		  {
            for(i=0;i<8;i++)
		      {
               position[8]+=1;              
			   position[9]-=1;             
			   position[10]+=1;            
			   position[11]-=1;       
			    PWM_24();     
                low_level_500u(40);
		       }		
			     delay10ms(1);
			for(i=0;i<20;i++)
		      {
               position[3]+=3;              
			   position[4]-=6;
			   position[5]-=3;             
			   position[8]+=2;            
			   position[9]-=2;        
			    PWM_24();   
                low_level_500u(70);
		
		      }
			     delay500ms(1);
			for(i=0;i<20;i++)
		      {
               position[3]-=3;              
			   position[4]+=6;
			   position[5]+=3;             
			   position[8]-=2;            
			   position[9]+=2;        
			    PWM_24();    
                low_level_500u(70);
		       }
			     delay10ms(1);
			for(i=0;i<8;i++)
		      {
               position[8]-=1;              
			   position[9]+=1;             
			   position[10]-=1;            
			   position[11]+=1;    
			    PWM_24();        
                low_level_500u(40);
		       }
			      
		   }
		     part++;
		}
             part-=2;
		  for(j=0;j<5;j++)                           
			{
			  for(i=0;i<1;i++)                           
			    {
			     position[13]+=19;
				 position[15]-=19;
				  PWM_24();
				 low_level_500u(50);
			    }
				   delay500ms(1);
			 }

			  for(i=0;i<19;i++)                           
			    {
			     position[12]+=5;
				 position[13]-=5;
				 position[14]-=5;
				 position[15]+=5;
				  PWM_24();
				 low_level_500u(40);
			    }
				  delay500ms(1);
	 	initial_position();		
}
//#############################################################################
// 函数名称：void qiaoxiyang_8()
// 函数说明：俏夕阳bye bye
// 入口参数：无
// 出口参数：无
//#############################################################################	

void xiyang_8(void)
{
 
      uchar i;
   
            for(i=0;i<20;i++)
		      {
			   position[7]+=3;  
           	   position[15]-=3;
               position[14]--;
			    PWM_24();
			   low_level_500u(40);
        	  }
			  
	        for(i=0;i<30;i++)
		      {
			   position[0]--;             
			   position[3]++;      
			    PWM_24();         
			   low_level_500u(40);
		      }
      			  delay1s(1);

  	        for(i=0;i<30;i++)
		      {
			   position[0]++;             
			   position[3]--;      
			    PWM_24();       
			   low_level_500u(40);
		      }
	        for(i=0;i<20;i++)
		      {
			   position[7]-=3;  
			   position[15]+=3;
 			   position[14]++;
			    PWM_24();
			   low_level_500u(40);
		      }
	 		initial_position();
}
//#############################################################################
// 函数名称：void qiaoxiyang_9()
// 函数说明：俏夕阳平移	1
// 入口参数：无
// 出口参数：无
//#############################################################################	
void xiyang_9(void)
{
           uchar j,i;
		    for(i=0;i<50;i++)
		      {
			   position[0]--;              //左腿下蹲
			   position[1]+=2;             
			   position[2]++;               
			   
               position[3]++;              //右腿下蹲
			   position[4]-=2;              
			   position[5]--;      
			    PWM_24();         
			   low_level_500u(50);
			  }
	 for(j=0;j<3;j++) 
	   {
	 	 for(i=0;i<15;i++)                   //向右侧身
		   {
			position[8]-=1;            
			position[9]+=1;            

            position[10]-=1;           
			position[11]+=1;           

		    position[13]-=4;
            position[15]+=4;
			 PWM_24();
            low_level_500u(50);
		   }  
         for(i=0;i<10;i++)                 
		   {
            position[3]+=1;                    
			position[4]-=2;               
			position[5]-=1;               
			position[10]-=1;              
			position[11]+=1;              

			position[13]-=3;
            position[15]+=3;
               PWM_24();
			low_level_500u(50);
		   }

	     for(i=0;i<10;i++)                
		   {
            position[3]-=1;              
			position[4]+=2;
			position[5]+=1;
			position[10]-=1;               
			position[11]+=1;              

			position[13]-=2;
            position[15]+=2;
               PWM_24();
			low_level_500u(50);
		   }
// ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈
		 for(i=0;i<50;i++)             
		   {
			position[8]+=1;            
			position[9]-=1;            

            position[10]+=1;           
			position[11]-=1;                          

		    position[13]++;
            position[15]--;

	        position[12]--;
		    position[14]++;
			    PWM_24();
			low_level_500u(50);
   		   }
	     for(i=0;i<20;i++)             
		   {
			position[8]-=1;            
			position[9]+=1;            
                
            position[13]+=2;
            position[15]-=2;

			position[12]-=2;
		    position[14]+=2;
				 PWM_24();
			low_level_500u(50);
   		   }
	     for(i=0;i<15;i++)                   //向右侧身
		   {
			position[8]-=1;            
			position[9]+=1;            

            position[10]-=1;           
			position[11]+=1;           
			
	        position[13]+=1;
            position[15]-=1;

			position[12]-=1;
		    position[14]+=1;

            if((i%3)==0)
			  {
			   position[13]++;
               position[15]--;

			   position[12]--;
		       position[14]++;
			  }
                PWM_24();
			  low_level_500u(50);
		    }


         for(i=0;i<55;i++)                   
		   {
		    position[12]+=2;
		    position[14]-=2;
			 PWM_24();
		    low_level_500u(50);
           }
	   }
	         for(i=0;i<50;i++)
		       {
			    position[0]++;             //左褪起立
			    position[1]-=2;            
			    position[2]--;             

                position[3]--;             //右腿起立
			    position[4]+=2;           
			    position[5]++;     
				 PWM_24();       
			     low_level_500u(50);    		
			   }
			     delay10ms(20);
				 initial_position();
}
//#############################################################################
// 函数名称：void qiaoxiyang_10()
// 函数说明：俏夕阳平移2	
// 入口参数：无
// 出口参数：无
//#############################################################################	

void xiyang_10(void)
{
           uchar j,i;
		    for(i=0;i<50;i++)
		      {
			   position[0]--;              //左腿下蹲
			   position[1]+=2;             
			   position[2]++;               
			   
               position[3]++;              //右腿下蹲
			   position[4]-=2;              
			   position[5]--;      
			    PWM_24();         
			   low_level_500u(50);
			  }
              
 	 for(j=0;j<3;j++) 
	   {
	 	 for(i=0;i<15;i++)             //向右侧身
		   {
			position[8]+=1;           
			position[9]-=1;           
			
            position[10]+=1;           
			position[11]-=1;           

		    position[13]-=4;
            position[15]+=4;
			 PWM_24();
            low_level_500u(50);
		   }  
         for(i=0;i<10;i++)                 
		   {
            position[0]-=1;                    
			position[1]+=2;               
			position[2]+=1;               
			position[8]+=1;               
			position[9]-=1;               
            position[13]-=3;
            position[15]+=3;
			 PWM_24();
            low_level_500u(50);
		   }

	     for(i=0;i<10;i++)                
		   {
            position[0]+=1;               
			position[1]-=2;
			position[2]-=1;
			position[8]+=1;               
			position[9]-=1;
			position[13]-=2;
            position[15]+=2;
			 PWM_24();
            low_level_500u(50);
		   }
//---------------------------------------------------------------------------------
         for(i=0;i<50;i++)             
		   {
			position[8]-=1;            
			position[9]+=1;            

            position[10]-=1;           
			position[11]+=1;                          

		    position[13]++;
            position[15]--;

	        position[12]--;
		    position[14]++;
			 PWM_24();
            low_level_500u(50);
   		   }
	     for(i=0;i<20;i++)             
		   {
			position[10]+=1;            
			position[11]-=1;            
			                
            position[13]+=2;
            position[15]-=2;

			position[12]-=2;
		    position[14]+=2;
				 PWM_24();
			low_level_500u(50);
   		   }
	     for(i=0;i<15;i++)             //向右侧身
		   {
			position[8]+=1;           
			position[9]-=1;           

            position[10]+=1;          
			position[11]-=1;          

	        position[13]+=1;
            position[15]-=1;

			position[12]-=1;
		    position[14]+=1;

            if((i%3)==0)
			  {
			   position[13]++;
               position[15]--;

			   position[12]--;
		       position[14]++;
			  }
                PWM_24();
			   low_level_500u(50);
		  }


          for(i=0;i<55;i++)                   
		    {
		     position[12]+=2;
		     position[14]-=2;
			  PWM_24();
		     low_level_500u(50);
            }
	
        }

			 for(i=0;i<50;i++)
		       {
			    position[0]++;             //左褪起立
			    position[1]-=2;            
			    position[2]--;             

                position[3]--;             //右腿起立
			    position[4]+=2;           
			    position[5]++;     
				 PWM_24();       
			     low_level_500u(50);    		
			   }
			     delay10ms(20);
				 initial_position();
}
//#############################################################################
// 函数名称：void  qiaoxiyang()
// 函数说明：俏夕阳
// 入口参数：无
// 出口参数：无
//#############################################################################	
void qiaoxiyang(void)
{                   
		     xiyang_6();
			 xiyang_4();
			 xiyang_3();
			 xiyang_5();
			 xiyang_2();
			 xiyang_9();
			 xiyang_1();
			 xiyang_7();
			 xiyang_10();
			 xiyang_1();
			 xiyang_8();			   
}