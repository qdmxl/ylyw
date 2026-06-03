#include <math.h>
//#include "REG15W4Kxx.h"
#include "delay.h"
#include "main.h"
#include "basal.h"	
//#############################################################################
// 函数名称：void dpzc_1(char m,uchar n)
// 函数说明：大鹏展翅
// 入口参数：无
// 出口参数：无
//#############################################################################
void dpzc_1(char m,uchar n)
{
   uchar i;
  switch(n)
	{
	  case 0:
             for(i=0;i<20;i++)
		     {
                position[8]+=1*m;           
                position[9]+=(-1)*m;        
			    position[10]+=1*m;         
                position[11]+=(-1)*m;      
			   PWM_24();
                    low_level_500u(45);
             }
			
			 break;

      case 1:
		     for(i=0;i<40;i++)
		     {
			    position[0]+=(-1)*m;      
                position[1]+=1*m;         
			    PWM_24();
                low_level_500u(45);
             }
			 
			 break;

      case 2:   
		     for(i=0;i<120;i++)
		     {
			    position[0]+=1*m;         
             
                if((i%2)==0)
			    {
		           position[12]+=(-1)*m;
			       position[14]+=1*m;
			    }

			    if((i%5)==0)
			    {
			       position[3]+=1*m;
			    }
			 PWM_24();
                    low_level_500u(20);
             }
			
			 break;
	  default: 
              break;
    }
}
//#############################################################################
// 函数名称：void yaobibaitou()
// 函数说明：摇臂摆头，展臂
// 入口参数：无
// 出口参数：无
//#############################################################################
void yaobibaitou(void)
{uchar i,j,k; 
//////////////////////////////////////////////摇臂加摆头
for(i=0;i<30;i++)
    {
	    position[0]-=2;             
	    position[2]--;              

	    position[3]+=2;             
		position[5]++;              

        position[6]-=4;
		position[7]+=4;
		 
			PWM_24();
                    low_level_500u(45);
	}
   for(j=0;j<3;j++)
    {
        for(i=0;i<2;i++)
        {	
	       position[12]=position_initial[12];
	       position[13]=position_initial[13]+100;
           position[14]=position_initial[14]+100;
	       position[15]=position_initial[15];
           position[16]=position_initial[16]-40;
           
		  PWM_24();
                    low_level_500u(45);
		   delay10ms(22);
		   
			    
           position[13]-=100;
           position[14]-=100;
	       position[16]=position_initial[16];
           PWM_24();
                    low_level_500u(45);
		   delay10ms(32);
	 
	   }
	       
           position[12]=position_initial[12]-100;
           position[15]=position_initial[15]-100;
	      position[16]=position_initial[16]+50;
        PWM_24();
                    low_level_500u(45);
		   delay10ms(72);
   }

    for(i=0;i<50;i++)
    {	
       position[12]+=2;
       position[15]+=2;
       position[16]-=1;
	   
       PWM_24();
                    low_level_500u(20);
	 
    }



    for(i=0;i<30;i++)
    {
	   position[0]+=2;              
	   position[2]++;              
	   
	   position[3]-=2;             
       position[5]--;              

       position[6]+=4;
  	   position[7]-=4;
      
       PWM_24();
                    low_level_500u(20);
		   
		     } 
/////////////////////////////////////////////展臂
for(k=0;k<3;k++)
	{	     
    for(i=0;i<2;i++)
    {
	   position[12]-=45;
	   position[13]+=45;
	   position[14]+=45;
       position[15]-=45;

       position[9]-=10;
       position[11]+=10;
		 PWM_24();
                    low_level_500u(20);
		   delay10ms(22);
    }			  
	for(i=0;i<2;i++)
    {
	   position[12]-=45;
	   position[13]-=90;
	   position[14]+=45;
       position[15]+=90;

       position[9]-=10;
       position[11]+=10;
		 PWM_24();
                    low_level_500u(20);
		   delay10ms(22);
    }
	  	   
    position[12]=position_initial[12];
    position[13]=position_initial[13];
    position[14]=position_initial[14];
    position[15]=position_initial[15];

    position[9]=position_initial[9];
    position[11]=position_initial[11];
		   
     PWM_24();
         low_level_500u(20);
		   delay10ms(22);
 }
}
//#############################################################################
// 函数名称：void dpzhch()
// 函数说明：大鹏展翅
// 入口参数：无
// 出口参数：无
//#############################################################################

void dpzhch(void)
{////////////////////////////////////////////////大鹏展翅
	uchar i,j,k;
	sit_down(44);
	for(j=0;j<5;j++)                 
		       {
               position[12]-=2;                    
			   position[14]+=2;                              
               PWM_24();
               low_level_500u(10);
		      }	
	for(i=0;i<3;i++)
   {  
      dpzc_1(1,i);
   } 
   for(j=0;j<3;j++)
   {
      k=75;
	  for(i=0;i<30;i++)
	  {
         position[3]--;            
	     position[4]+=2;           
		 position[5]++;           

         position[12]-=3;
	     position[14]+=3;

	    
		PWM_24();
		 low_level_500u(k);
       
		k--;
	  }
      
	  k=75;
	  for(i=0;i<30;i++)
	  {
         position[3]++;            
		 position[4]-=2;           
		 position[5]--;            
		 position[12]+=3;
	     position[14]-=3;

		
		PWM_24();
		 low_level_500u(k);
       
		k++;
	  }
   }

   for(i=0;i<3;i++)
   {
      dpzc_1(-1,2-i);
   }
            for(j=0;j<5;j++)                 
		       {
               position[12]+=2;                    
			   position[14]-=2;                              
               PWM_24();
               low_level_500u(10);
		      }
   stand_up(44);
}
//#############################################################################
// 函数名称：void shou_dd(void)
// 函数说明：手臂抖动
// 入口参数：无
// 出口参数：无
//#############################################################################

void shou_dd(uchar a)
{
    uchar i,j,m=0;
	for(i=0;i<110;i++)
    {
	    position[6]--;
		position[7]++;
		position[12]--; 
        position[14]++;
		PWM_24();
		 low_level_500u(20);
    }

	for(i=0;i<5;i++)
    {
	    position[6]-=3;
        position[7]++;
		PWM_24();
		 low_level_500u(20);
    }
   
    position[16]+=50;
    PWM_24();
		 low_level_500u(20);

    for(j=0;j<a;j++)
	{
		for(i=0;i<40;i++)
		{
		   position[13]--; 

		   if((i%2)==0)
		   {
		     position[16]--;
		   }

		PWM_24();
		 low_level_500u(10);
		}

        for(i=0;i<40;i++)
		{
		   position[12]--;
		   position[13]+=3; 

		   if((i%2)==0)
		   {
		     position[16]--;
		   }

		 PWM_24();
		 low_level_500u(10);
		}

		for(i=0;i<40;i++)
		{
		   position[12]++;
           position[13]-=2;
		   position[14]++;
 		   position[15]-=2;

		   if((i%2)==0)
		   {
		     position[16]--;
		   }

	PWM_24();
		 low_level_500u(10);
		}

		for(i=0;i<40;i++)
		{
		   position[14]--;
		   position[15]++; 

		   if((i%2)==0)
		   {
		     position[16]--;
		   }

		 PWM_24();
		 low_level_500u(10);
		}

        for(i=0;i<40;i++)
		{
		   position[15]++; 

		   if((i%2)==0)
		   {
		     position[16]--;
		   }

		PWM_24();
		 low_level_500u(10);
		}

		position[6]+=10;
		position[7]-=10;
		PWM_24();
		 low_level_500u(10);
//------------------------------------

        for(i=0;i<40;i++)
		{
		   position[15]++; 

		   if((i%2)==0)
		   {
		     position[16]++;
		   }

		PWM_24();
		 low_level_500u(10);
		}

        for(i=0;i<40;i++)
		{
		   position[14]++;
		   position[15]-=3; 

		   if((i%2)==0)
		   {
		     position[16]++;
		   }

		 PWM_24();
		 low_level_500u(10);
		}

		for(i=0;i<40;i++)
		{
		   position[14]--;
           position[15]+=2;
		   position[12]--;
 		   position[13]+=2;

		   if((i%2)==0)
		   {
		     position[16]++;
		   }

		 PWM_24();
		 low_level_500u(10);
		}

		for(i=0;i<40;i++)
		{
		   position[12]++;
		   position[13]--;
 
		   if((i%2)==0)
		   {
		     position[16]++;
		   }

		   PWM_24();
		 low_level_500u(10);
		}

        for(i=0;i<40;i++)
		{
		   position[13]--; 

		   if((i%2)==0)
		   {
		     position[16]++;
		   }

		PWM_24();
		 low_level_500u(10);
		}

		position[6]+=10;
		position[7]-=10;
		PWM_24();
		 low_level_500u(10);
   }

   position[16]-=50;
  PWM_24();
		 low_level_500u(15);
   for(i=0;i<110;i++)
   {
		position[12]++; 
        position[14]--;
		PWM_24();
		 low_level_500u(15);
   }

   for(i=0;i<(110-a*20);i++)
   {
	    position[6]++;
		position[7]--;
		PWM_24();
		 low_level_500u(15);
   }

   for(i=0;i<5;i++)
   {
	    position[6]+=3;
        position[7]--;
		PWM_24();
		 low_level_500u(15);
   }
}
//----------------------------------------------------------------------------------------------------------------
void qhzy_niu_2(uchar m)
{
    uchar i,j;
    for(j=0;j<m;j++)                   
	{
        for(i=0;i<25;i++)             
		{
			position[0]+=3;           
		    position[1]-=2;           

            position[3]-=3;           
			position[4]+=2;          
            
			 PWM_24();
                    low_level_500u(45);
	    }

		for(i=0;i<25;i++)             
		{
			position[0]-=3;           
			position[1]+=2;           

            position[3]+=3;           
			position[4]-=2;          
         PWM_24();
                    low_level_500u(45);
	    }
    }
}
//#############################################################################
// 函数名称：void qhzy_niu()
// 函数说明：前后左右扭
// 入口参数：无
// 出口参数：无
//#############################################################################
void qhzy_niu(void)                       //前后扭
{
   uchar i,j;
  sit_down(50);
  ////////////////////////////////


   position[6]-=60;                    
   PWM_24();
   low_level_500u(20);	
       
   delay1s(1);              
   position[7]+=60;                
   PWM_24();
   low_level_500u(20);
   delay500ms(1);
   
   position[13]+=80;                 
   PWM_24();
   low_level_500u(20);
   delay500ms(1);
      
   position[15]-=80;                       
   PWM_24();
   low_level_500u(20);
   delay500ms(1);
   
   qhzy_niu_2(2);

   position[13]-=160;         
   position[15]+=160;                    
   PWM_24();
   low_level_500u(20);
   delay500ms(1);
   qhzy_niu_2(2);

   position[13]+=80;          
   position[15]-=80;         
   PWM_24();
   low_level_500u(20);
   delay500ms(1);
//----------------------------------------------------------------------------------------------------------------
 for(i=0;i<2;i++)
 {
 stand_up(20);
 delay500ms(1);
 sit_down(20);
 delay500ms(1);
 
 }
 ////////////////////////////////////////////
 position[13]-=80;                         
 PWM_24();
 low_level_500u(20);
 delay500ms(1);

   position[15]+=80;               
   PWM_24();
   low_level_500u(20);
		
   delay1s(1);

   for(j=0;j<2;j++)
   {
     for(i=0;i<15;i++)          
     {
	   position[8]++;          
	   position[9]--;          

       position[10]++;          
	   position[11]--;          
                
	PWM_24();
		 low_level_500u(65);
		
	 }

	 for(i=0;i<15;i++)                  
     {
	   position[8]--;          
	   position[9]++;           

       position[10]--;          
	   position[11]++;         
	
	  PWM_24();
		 low_level_500u(65);
 	 }

	 for(i=0;i<15;i++)                 
     {
	   position[8]--;            
	   position[9]++;        
       position[10]--;          
	   position[11]++;           
                
	  PWM_24();
		 low_level_500u(65);
 	 }

	 for(i=0;i<15;i++)                  
     {
	   position[8]++;          
	   position[9]--;            
       position[10]++;           
	   position[11]--;           
                
	  PWM_24();
		 low_level_500u(65);
	 }
   }

   for(i=0;i<60;i++)
   {
     position[6]++;
     position[7]--;
     position[13]++;           
     position[15]--;          
     if((i%3)==0)
	 {
	   position[13]++;         
       position[15]--;         
	 }

  PWM_24();
		 low_level_500u(20);
   }
   stand_up(50);
 
}
//#############################################################################
// 函数名称：void hfh_r()
// 函数说明：黄飞鸿
// 入口参数：无
// 出口参数：无
//#############################################################################
void hfh_r(void)
{ uchar i,j;
            for(i=0;i<10;i++)
		      {
               position[6]+=1;              
			   position[7]-=1;             
			   PWM_24();
		 low_level_500u(20);
		      }
			 for(i=0;i<50;i++)
		      {
               position[12]-=2;            
			   position[14]+=2;             
			 PWM_24();
                    low_level_500u(45);
		      }
	           sit_down(50);
			   delay10ms(20);   
			    for(i=0;i<50;i++)
		      {
               position[6]-=2;              
			   position[7]+=2;              
			   position[12]+=2;             
			   position[14]-=2;            
              PWM_24();
                    low_level_500u(45);
		      }
			for(i=0;i<10;i++)
		      {
               position[0]-=1;              
			   position[1]+=2;             
			   position[2]+=1;             
			   position[3]-=5;              
			   position[4]+=10;              
			   position[5]+=5;             
			   position[6]-=8;            
			   position[7]+=10;            
			   position[10]-=4;            
			   position[11]+=4;            
			   position[12]-=5;            
			   position[13]+=5;            
			   position[14]+=10;          
			   position[15]-=5;           
			   position[16]-=5;            
                PWM_24();
    low_level_500u(35);
		delay10ms(4);
		
		      }
			     delay10ms(20);
	        for(j=0;j<3;j++)
		   {
			for(i=0;i<5;i++)
		      {
               position[15]-=10;             
			         PWM_24();
                    low_level_500u(55);
		      }
			for(i=0;i<5;i++)
		      {
               position[15]+=10;           
			      PWM_24();
                    low_level_500u(55);
		      }
		   }
		        delay10ms(30);
		    for(i=0;i<10;i++)
		      {
               position[0]+=1;            
			   position[1]-=2;            
			   position[2]-=1;            
			   position[3]+=5;             
			   position[4]-=10;            
			   position[5]-=5;             
			   position[6]+=18;              
			   position[7]-=20;             
			   position[10]+=4;              
			   position[11]-=4;              
			   position[12]+=5;              
			   position[13]-=5;            
			   position[14]-=10;             
			   position[15]+=5;             
			   position[16]+=5;            
               PWM_24();
    low_level_500u(30);
		       delay10ms(4);
		      }
			    stand_up(50);
				initial_position();              //初始位置
}
//#############################################################################
// 函数名称：void hfh_l()
// 函数说明：黄飞鸿
// 入口参数：无
// 出口参数：无
//#############################################################################
void hfh_l(void)
{ 
            uchar i,j;
              for(i=0;i<10;i++)
		      {
               position[6]+=1;              
			   position[7]-=1;              
			   PWM_24();
		 low_level_500u(20);
		      }
			 for(i=0;i<50;i++)
		      {
               position[12]-=2;             
			   position[14]+=2;            
			   PWM_24();
                    low_level_500u(45);
		      }
	           sit_down(50);
			   delay10ms(20);   
			    for(i=0;i<50;i++)
		      {
               position[6]-=2;              
			   position[7]+=2;             
			   position[12]+=2;              
			   position[14]-=2;             
                PWM_24();
                    low_level_500u(45);
		      }
			for(i=0;i<10;i++)
		      {
               position[0]+=5;              
			   position[1]-=10;             
			   position[2]-=5;             
			   position[3]+=1;             
			   position[4]-=2;              
			   position[5]-=1;             
			   position[6]-=10;             
			   position[7]+=8;            
			   position[8]+=4;             
			   position[9]-=4;             
			   position[12]-=10;            
			   position[13]+=5;             
			   position[14]+=5;             
			   position[15]-=5;             
			   position[16]+=5;            
               PWM_24();
               low_level_500u(45);
		       delay10ms(4);
		      }
			     delay10ms(20);
	        for(j=0;j<3;j++)
		   {
			for(i=0;i<5;i++)
		      {
               position[13]+=10;             
			   PWM_24();
               low_level_500u(55);
		    
		      }
			for(i=0;i<5;i++)
		      {
               position[13]-=10;            
			   PWM_24();
               low_level_500u(55);
		      }
		   }
		        delay10ms(30);
		    for(i=0;i<10;i++)
		      {
               position[0]-=5;              
			   position[1]+=10;             
			   position[2]+=5;              
			   position[3]-=1;             
			   position[4]+=2;              
			   position[5]+=1;              
			   position[6]+=10;              
			   position[7]-=8;              
			   position[8]-=4;             
			   position[9]+=4;              
			   position[12]+=10;           
			   position[13]-=5;             
			   position[14]-=5;              
			   position[15]+=5;              
			   position[16]-=5;              
               PWM_24();
               low_level_500u(35);
		       delay10ms(4);
		      }
			    stand_up(50);
				initial_position();              //初始位置
}
//#############################################################################
//函数名称： void l_pyi(uchar step)
//函数说明：舞蹈左平移子程序
//入口参数：step, 表示左平移次数。
//出口参数：无
//#############################################################################
void wdl_pyi(uchar step)
{
       uchar j,i;            
         sit_down(20);
		 for(j=0;j<5;j++)                 
		       {
               position[12]-=2;                    
			   position[14]+=2;                              
               PWM_24();
               low_level_500u(10);
		      }
		delay500ms(1);
		
        for(i=0;i<step;i++)
		  {
	        for(j=0;j<15;j++)             
		       {
			    position[8]++;              
			    position[9]--;             

                position[10]++;             
			    position[11]--;          

                PWM_24();
                    low_level_500u(30);
		
			   }  
             for(j=0;j<10;j++)                 
		       {
               position[0]--;                    
			   position[1]++;               
               position[1]++;
			   position[2]++;               
			   position[8]++;               
			   position[9]--;               
             PWM_24();
                    low_level_500u(30);
		      }

			for(j=0;j<10;j++)                
		      {
               position[0]++;               
			   position[1]--;
               position[1]--;
			   position[2]--;
			   position[8]++;               
			   position[9]--;               
        PWM_24();
                    low_level_500u(30);
		       }

            for(j=0;j<50;j++)             
		       {
			    position[8]--;            
			    position[9]++;            

                position[10]--;           
			    position[11]++;           
            PWM_24();
                    low_level_500u(20);
   		        }
			 for(j=0;j<20;j++)             
		        {
			    position[10]++;            
			    position[11]--;            
             PWM_24();
                    low_level_500u(20);
   		        }
			 for(j=0;j<15;j++)                  
		        {
			    position[8]++;            
			    position[9]--;           

                position[10]++;          
			    position[11]--;           
              PWM_24();
                    low_level_500u(30);
			   }
           }
		   delay500ms(1);
		   for(j=0;j<5;j++)                 
		       {
               position[12]+=2;                    
			   position[14]-=2;                              
               PWM_24();
               low_level_500u(10);
		      }
	        stand_up(20);
			
}			
//#############################################################################
//函数名称： void r_pyi(uchar step)
//函数说明：舞蹈右平移子程序
//入口参数：step, 表示右平移次数。
//出口参数：无
//#############################################################################
void wdr_pyi(uchar step)
{
    uchar j,i;
             
          sit_down(20);
		  for(j=0;j<5;j++)                 
		       {
               position[12]-=2;                    
			   position[14]+=2;                              
               PWM_24();
               low_level_500u(10);
		      }
		 delay500ms(1);
		 
        for(i=0;i<step;i++)
		  {
	        for(j=0;j<15;j++)                  
		       {
			    position[8]--;           
			    position[9]++;           

                position[10]--;           
			    position[11]++;          

             PWM_24();
                    low_level_500u(30);
			  
		
			   }  
             for(j=0;j<10;j++)                 
		       {
               position[3]++;                    
			   position[4]--;               
               position[4]--;
			   position[5]--;               
			   position[10]--;               
			   position[11]++;             
              
			PWM_24();
                    low_level_500u(30);
		      }

			for(j=0;j<10;j++)                
		      {
               position[3]--;               
			   position[4]++;
               position[4]++;
			   position[5]++;
			   position[10]--;               
			   position[11]++;             
              
			PWM_24();
                    low_level_500u(30);
		       }

            for(j=0;j<50;j++)             
		       {
			    position[8]++;            
			    position[9]--;            

                position[10]++;          
			    position[11]--;           
              PWM_24();
                    low_level_500u(20);
			
   		        }
			 for(j=0;j<20;j++)            
		        {
			    position[8]--;            
			    position[9]++;            
               PWM_24();
                    low_level_500u(20);
			    
   		        }
			 for(j=0;j<15;j++)                  
		        {
			    position[8]--;            
			    position[9]++;            

                position[10]--;           
			    position[11]++;          

                PWM_24();
                    low_level_500u(30);
			   }
           } 
		   delay500ms(1);
		   for(j=0;j<5;j++)                 
		       {
               position[12]+=2;                    
			   position[14]-=2;                              
               PWM_24();
               low_level_500u(10);
		      }
		    stand_up(20);
			   
}
//#############################################################################
// 函数名称：void jiewu()
// 函数说明：街舞
// 入口参数：无
// 出口参数：无
//#############################################################################

void jiewu(void)
{	initial_position();	
	   delay500ms(1);
    yaobibaitou();	  		    //摇臂摆头，展臂
	 delay500ms(1);
    dpzhch();					//大棚展翅
     delay500ms(1);
	shou_dd(5);					//双手抖动c
	 delay500ms(1);				
	 qhzy_niu();					//前后左右扭
	 delay500ms(1);
	switch (part)
	{case 1: 
 	 case 3:
	 case 5:
 	 case 7:
	 case 9:
	 case 11:        wdl_pyi(3);
	                  delay500ms(1);
		  	        fwc(4);
					  delay500ms(1);
					hfh_r();          //黄飞鸿右手
					   delay500ms(1);
					wdr_pyi(3);
					   delay500ms(1);
					break;
	 case 2:   
	 case 4:
	 case 6:
	 case 8: 
	 case 10:
	 case 12: 
	 	  			 wdr_pyi(3);
					  delay500ms(1);
		 			 fwc(4);
					  delay500ms(1);
					 hfh_l();          //黄飞鸿左手
					  delay500ms(1);
					 wdl_pyi(3);
					  delay500ms(1);
					  break;
		  default: 
                      break;			   
	
	} 
	dpzhch();					//大棚展翅	
	delay500ms(1);

	yaobibaitou();	  		    //摇臂摆头，展臂
	delay500ms(1);

	jingli_r();                 //右手敬礼
	delay500ms(1);
	jingli_l();                 //左手敬礼
    delay500ms(1);
 } 