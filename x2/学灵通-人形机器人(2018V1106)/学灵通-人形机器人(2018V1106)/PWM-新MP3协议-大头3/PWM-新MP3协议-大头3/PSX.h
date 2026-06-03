/*
******************PSX操作文件**************
*/
#ifndef PSX_2015_H
#define PSX_2015_H

#define SPIF 0x80
#define WCOL 0x40	

#define SSIG 0x80
#define SPEN 0x40	
#define DORD 0x20	
#define MSTR 0x10	
#define CPOL 0x08	
#define CPHA 0x04	

#define SPDHH 0x00	
#define SPDH  0x01	
#define SPDL  0x02	
#define SPDLL 0x03	

#define ESPI 0x02   
#define NSPI 0xFD  

sbit SPISS = P5^4;         //从器件控制端引脚

bit psx_mode_flag =  0;		 //手柄模式切换标志位

uchar psx_mode = 0x41;  
uchar psx_key = 0xFF;
uchar psx_key_buff = 0xFF;
uchar psx_key_buff_flag = 0x00;

bit anjian_bit;
bit anjian_bit_flag;

//=================================================================
void Delay3us_PSX(void)		//@22.1184MHz
{
	unsigned char i;

	_nop_();
	_nop_();
	_nop_();
	i = 5;
	while (--i);
}
//================================================================
void Delay1us_PSX(void)		//@22.1184MHz
{
	_nop_();
	_nop_();
	_nop_();
}

//=================================================================
void Init_SPI(void)		 
{
	//P_SW1 &= 0xF3;
	P_SW1 |= 0x08;
	SPDAT = 0x00;         
	SPSTAT = SPIF | WCOL; 
	SPCTL = SPEN | MSTR | SSIG | CPHA | CPOL | DORD  | SPDLL;

  SPISS = 1;
	IE2 &= NSPI;          
}

//==================================================================
void Clear_PSXBuff(void)
{
	unsigned char i = 0, j = 0;
	uchar psx_buff[9] = {0};

	SPISS = 0;  
  Delay1us_PSX();/////////+++++++++++++++++  
	while(i < 9)
	{
		if(i == 0)
			j = 0x01;
		else 
		{
			if(i == 1)
				j = 0x42;
			else j = 0xFF;
		}
		SPDAT = j;                     
		while((SPSTAT & 0x80) != SPIF);
		SPSTAT = SPIF | WCOL;          
		psx_buff[i] = SPDAT;
		Delay3us_PSX();
		i++;
	}
	SPISS = 1;    
}
//===================================================================
void Obtain_PSXCode(void)
{
	unsigned char i = 0, j = 0;
	uchar psx_buff[9] = {0};
	uint psx_key_buff = 0;

	SPISS = 0; 
  Delay1us_PSX();////////++++++++++++++++
	while(i < 9)
	{
		if(i == 0)
			j = 0x01;
		else 
		{
			if(i == 1)
				j = 0x42;
			else j = 0xFF;
		}
		SPDAT = j; 		
		while((SPSTAT & 0x80) != SPIF);		
		SPSTAT = SPIF | WCOL;          
		psx_buff[i] = SPDAT;
		Delay3us_PSX();
		i++;
	}
	SPISS = 1;
	if(psx_buff[1] != 0xFF)
	{    
		if(psx_buff[1] != psx_mode)
		{
			psx_mode = psx_buff[1];
			psx_key = 42;
			return;		
		}
	}
	psx_key_buff = psx_buff[3] << 8;
	psx_key_buff = psx_key_buff | psx_buff[4];
	if(psx_key_buff != 0xFFFF)
	{
		switch(psx_key_buff)
		{
			case 0xEFFF: psx_key = 1; break;  
			case 0xDFFF: psx_key = 2; break;  
			case 0xBFFF: psx_key = 3; break;  
			case 0x7FFF: psx_key = 4; break;  

			case 0xFFEF: psx_key = 5; break;  
			case 0xFFDF: psx_key = 6; break;  
			case 0xFFBF: psx_key = 7; break;  
			case 0xFF7F: psx_key = 8; break;  

			case 0xEFEF: psx_key = 9; break;  
			case 0xEFDF: psx_key = 10; break;  
			case 0xEFBF: psx_key = 11; break;  
			case 0xEF7F: psx_key = 12; break;  
			case 0xDFEF: psx_key = 13; break;  
			case 0xDFDF: psx_key = 14; break;  
			case 0xDFBF: psx_key = 15; break;  
			case 0xDF7F: psx_key = 16; break;  
			case 0xBFEF: psx_key = 17; break;  
			case 0xBFDF: psx_key = 18; break;  
			case 0xBFBF: psx_key = 19; break;  
			case 0xBF7F: psx_key = 20; break;  
			case 0x7FEF: psx_key = 21; break;  
			case 0x7FDF: psx_key = 22; break;  
			case 0x7FBF: psx_key = 23; break;  
			case 0x7F7F: psx_key = 24; break;  

			case 0xFFF0: psx_key = 25; break;  
			case 0xFFF1: psx_key = 26; break;  
			case 0xFFF2: psx_key = 27; break;  
			case 0xFFF3: psx_key = 28; break;  
			case 0xFFF4: psx_key = 29; break;  	
			case 0xFFF5: psx_key = 30; break;  
			case 0xFFF6: psx_key = 31; break;  
			case 0xFFF7: psx_key = 32; break;  
			case 0xFFF8: psx_key = 33; break;  	 
			case 0xFFF9: psx_key = 34; break;  
			case 0xFFFA: psx_key = 35; break;  
			case 0xFFFB: psx_key = 36; break;  
			case 0xFFFC: psx_key = 37; break;  	 
			case 0xFFFD: psx_key = 38; break;  
			case 0xFFFE: psx_key = 39; break;  

			case 0xFEFF: psx_key = 40; break;  
			case 0xF7FF: psx_key = 41; break;  
			case 0xF6FF: psx_key = 0;  break;  
			case 0xFDFF: psx_key = 43; break;  
			case 0xFBFF: psx_key = 44; break;  
			case 0xF9FF: psx_key = 45; break;

			default: psx_key = 0xFF;break;
		}
		if(psx_key != 0xFF)
			return;
	}else psx_key = 0xFF;
	if(psx_buff[1] == 0x73)
	{	
		psx_buff[0] = 0;
		if(psx_buff[7] == 0x00)
			psx_buff[0] |= 0x80;     	
		else
		{
			if(psx_buff[7] == 0xFF)
				psx_buff[0] |= 0x40; 			
		}
		if(psx_buff[8] == 0x00)
			psx_buff[0] |= 0x20;     
		else
		{
			if(psx_buff[8] == 0xFF)
				psx_buff[0] |= 0x10; 			
		}
		if(psx_buff[5] == 0x00)
			psx_buff[0] |= 0x08;     
		else
		{
			if(psx_buff[5] == 0xFF)
				psx_buff[0] |= 0x04; 				
		}
		if(psx_buff[6] == 0x00)
			psx_buff[0] |= 0x02;    
		else
		{
			if(psx_buff[6] == 0xFF)
				psx_buff[0] |= 0x01; 			
		}
		switch(psx_buff[0])
		{
			case 0x20: psx_key = 51; break;     
			case 0x40: psx_key = 52; break;  
			case 0x10: psx_key = 53; break;  
			case 0x80: psx_key = 54; break;  

			case 0x02: psx_key = 55; break;  	     
			case 0x04: psx_key = 56; break;  
			case 0x01: psx_key = 57; break;  
			case 0x08: psx_key = 58; break;  

		/*	case 0x22: psx_key = 59; break;  	     
			case 0x24: psx_key = 60; break;  
			case 0x21: psx_key = 61; break;  
			case 0x28: psx_key = 62; break;  
			case 0x42: psx_key = 63; break;  	 			       
			case 0x44: psx_key = 64; break;  
			case 0x41: psx_key = 65; break; 
			case 0x48: psx_key = 66; break;  
			case 0x12: psx_key = 67; break;   			        
			case 0x14: psx_key = 68; break;  
			case 0x11: psx_key = 69; break;  
			case 0x18: psx_key = 70; break;  
			case 0x82: psx_key = 71; break;                    
			case 0x84: psx_key = 72; break;  
			case 0x81: psx_key = 73; break;  
			case 0x88: psx_key = 74; break;  */
			default: psx_key = 0xFF;break;			
		}				  
	}		
}
//========================================================================
void PSXKey_Filter(void)
{
	if((psx_key != 0xFF) && (psx_key != 42))
	{
		if(psx_mode == 0x41)
		{
			if((psx_key == 1) || (psx_key == 3))
				anjian_bit_flag = 1;
		}
		else
		{
			if((psx_key == 51) || (psx_key == 53))
				anjian_bit_flag = 1;			
		}
		if(psx_key_buff != psx_key)
		{
			psx_key_buff = psx_key;
			psx_key_buff_flag = 0;
			psx_key = 0xFF;
		} 
		else 
		{
			psx_key_buff_flag++;
			if(psx_key_buff_flag < 3)
				psx_key = 0xFF;
		}			
	}
	else
	{
		if(anjian_bit_flag == 1)
		{
			anjian_bit = 1;
			anjian_bit_flag = 0;
		}
	}
}

#endif


















