extern void low_level_t0(unsigned short int THTL);  //固定
extern void t0_init(void);							//
extern void array();
extern void initial_position(void);
extern void initial_position_slow(void);
extern void initial_position_slowOne(uchar k);
extern void low_level_500u(unsigned short int time);
extern void ForwardDelay(void);
extern void BackDelay(void);
extern unsigned char total;			    //千手观音总共的台数M
extern unsigned char part;				//本机所属台数N
extern unsigned char change;			//每个动作的变化量S

extern unsigned char position[24];         //用于记录24个舵机的位置
//extern signed short int jichu[24];			   //E2PROM程序用，最开始为初始位置
//extern signed short int position_change[24];
extern unsigned char arr[8];
extern unsigned char pick_up[8]; 
extern unsigned char position_initial[24];
extern int position_change[24];
extern unsigned char t0bit;
extern void p_to_p(int delay,int define);
extern int max(unsigned char total,int M);
extern void relative(int a1,int a2,int a3,int a4,int a5,int a6,int a7,int a8,int a9,\
              int a10,int a11,int a12,int a13,int a14,int a15,int a16,int a17,int a18,\
			  int a19,int a20,int a21,int a22,int a23,int a24);
extern void  sit_down(unsigned char step);
extern void  stand_up(unsigned char step);
extern void  turn_left(unsigned char step);	
extern void  turn_right(unsigned char step);
extern void  l_pyi(unsigned char step);
extern void  r_pyi(unsigned char step);
extern void  fwc(unsigned char step);
extern void  goal_l(unsigned char step);
extern void  goal_r(unsigned char step);
extern void  hp(void);
extern void  hpq(void);
extern void  yangwoqizuo(unsigned char step);
extern void  jingli_l(void);
extern void  jingli_r(void);
extern void  qianpaxia(void);
extern void  qianpq(void);
extern void  qgf(void);
extern void  hgf(void);
//extern void  qianshou(void);   

extern void daoli(void);
extern void pch(void);
extern void dt_l(void);
extern void dt_r(void);
extern void taijiaozi(void);
extern void wudao(void);
extern void fuwei(void);
extern void zuogouqiu(void);
extern void yougouqiu(void);
