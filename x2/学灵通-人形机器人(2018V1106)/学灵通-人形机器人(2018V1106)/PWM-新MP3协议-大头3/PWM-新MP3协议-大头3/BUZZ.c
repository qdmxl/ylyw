
#include "REG15W4Kxx.h"
#include "delay.h"

sbit fengming = P4^5;		  			  //·äÃùÆ÷


void fm300ms(uchar i)						//300ms¼ä¶Ï·äÃùÆ÷Ïì
{uchar j;	
for(j=0;j<i;j++)
{
	 fengming=0;
	 delay10ms(30);
	 fengming=1;
	 delay10ms(30);
 }
}
void fm200ms(uchar i)						//200ms¼ä¶Ï·äÃùÆ÷Ïì
{uchar j;	 
for(j=0;j<i;j++)
{
	 fengming=0;
	 delay10ms(20);
	 fengming=1;
	 delay10ms(20);
 }
}

void fm100ms(uchar i)						//100ms¼ä¶Ï·äÃùÆ÷Ïì
{uchar j;	 
for(j=0;j<i;j++)
{
	 fengming=0;
	 delay10ms(10);
	 fengming=1;
	 delay10ms(10);
 }
}
void fm50ms(uchar i)						//50ms¼ä¶Ï·äÃùÆ÷Ïì
{uchar j;	 
for(j=0;j<i;j++)
{
	 fengming=0;
	 delay10ms(5);
	 fengming=1;
	 delay10ms(5);
 }
}

void fm1ms(uchar i)						//100us¼ä¶Ï·äÃùÆ÷Ïì
{
	uchar j;	 
	for(j=0;j<i;j++)
	{
		 fengming=0;
		 delay1ms(1);
		 fengming=1;
		 delay1ms(1);
	 }
}











