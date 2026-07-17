// *Fundamentals of objective oriented programming
// Terinary Expression Conditional Statement
// #include<iostream>
// using namespace std;
// int main()
// {
// int x=10;
// cout<<(x>0?"x is positive": "x is negative" );
// return 0;
// }

// Nested Terinary condition
// #include<iostream>
// using namespace std;
// int main()
// {
//     int x = 0;
//     cout<<((x>0)?"x is positive":(x<0)?"x is negative":"x is zero")<<endl;
//     return 0;
// }
// For loop
// Basic for loop
// #include<iostream>
// using namespace std;
// int main()
// {
// int i=0;
// for(int i=0;i<10;i++){
// cout<<i<<" ";
// }
// return 0;
// }

// // For each loop
//  #include<iostream>
//  using namespace std;
//  int main()
//  {
//      int numbers[]={1, 2, 3, 4, 5};
//      for (int num : numbers){
//          cout<<num<<" ";
             
//     //if we just printed 3 ,break outof the loop immediately
//     if(num == 3){
//         break;
//     }
//     }
//     cout<<endl;
//     return 0;
//  }

// For loop with multiple variables 
// #include<iostream>
// using namespace std;
// int main()
// {
//     for(int i=0,j=10;i<5&&j>0;i++,j--)
//     {
//         cout<<"i="<<i<<"j="<<j<<"   "<<endl;
//     }
//     return 0;
// }
  
// Nested for loop
#include<iostream>
using namespace std;
int main()
{
    for(int i=1;i<=3;i++){
        for(int j=4;j>0;j--){
            cout<<" "<<i*j;
        }
        cout<<endl;
        }
        return 0;
    }
