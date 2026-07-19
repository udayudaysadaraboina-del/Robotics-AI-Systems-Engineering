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
// #include<iostream>
// using namespace std;
// int main()
// {
//     for(int i=1;i<=3;i++){
//         for(int j=4;j>0;j--){
//             cout<<" "<<i*j;
//         }
//         cout<<endl;
//         }
//         return 0;
//     }
// Order of growth
#include <iostream>
#include <vector>

using namespace std;

// 1. Constant Time -> O(1)
// No matter how big the vector is, it only does 1 step.
void printFirstElement(const vector<int>& arr) {
    if (!arr.empty()) {
        cout << "First element: " << arr[0] << endl; // 1 step
    }
}

// 2. Linear Time -> O(n)
// It has 1 single loop. If the array size is 'n', it runs 'n' times.
void printAllElements(const vector<int>& arr) {
    for (int num : arr) { // Runs n times
        cout << num << " ";
    }
    cout << endl;
}

// 3. Quadratic Time -> O(n^2)
// Nested loops! For every element, it loops through all elements again.
void printAllPairs(const vector<int>& arr) {
    int n = arr.size();
    for (int i = 0; i < n; i++) {       // Runs n times
        for (int j = 0; j < n; j++) {   // Runs n times for every i
            cout << "(" << arr[i] << ", " << arr[j] << ") ";
        }
        cout << endl;
    }
}

int main() {
    vector<int> numbers = {10, 20, 30, 40};

    cout << "--- O(1) Demo ---" << endl;
    printFirstElement(numbers);

    cout << "\n--- O(n) Demo ---" << endl;
    printAllElements(numbers);

    cout << "\n--- O(n^2) Demo ---" << endl;
    printAllPairs(numbers);

    return 0;
}