#include <adios2.h>
#include <mpi.h>
#include <vector>
#include <iostream>
int main(int argc,char**argv){
 MPI_Init(&argc,&argv);int rank,n;MPI_Comm_rank(MPI_COMM_WORLD,&rank);MPI_Comm_size(MPI_COMM_WORLD,&n);
 try{
  if(argc!=2||n!=8)throw std::runtime_error("Require output path and eight ranks");
  adios2::ADIOS adios("/users/vlad777/ADIOS2-Examples/adios2.xml",MPI_COMM_WORLD);
  auto io=adios.DeclareIO("PDFAnalysisOutput");
  auto u=io.DefineVariable<double>("U/pdf",{256,100},{static_cast<size_t>(rank)*32,0},{32,100});
  auto v=io.DefineVariable<double>("V/pdf",{256,100},{static_cast<size_t>(rank)*32,0},{32,100});
  auto writer=io.Open(argv[1],adios2::Mode::Write);
  std::vector<double> a(3200),b(3200);
  for(int step=0;step<3600;step++){
   std::fill(a.begin(),a.end(),step+rank*.001);std::fill(b.begin(),b.end(),-step-rank*.001);
   writer.BeginStep();writer.Put(u,a.data());writer.Put(v,b.data());writer.EndStep();
  }
  writer.Close();if(!rank)std::cout<<"Completed 3600 BP5 steps\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";MPI_Abort(MPI_COMM_WORLD,1);}
 MPI_Finalize();return 0;
}
