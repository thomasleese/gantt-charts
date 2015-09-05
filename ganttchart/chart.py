from collections import namedtuple


Block = namedtuple('Block', ['task', 'start', 'end'])


class Chart:
    def __init__(self, project):
        graph = [(task, [dep.dependency for dep in task.dependencies]) for task in project.tasks]
        print(graph)

        self.graph = self.topolgical_sort(graph)
        self.blocks = []

        start_times = {}
        finish_times = {}

        for entry in self.graph:
            task = entry[0]
            if entry[1]:
                start_times[task] = max(finish_times[t] for t in entry[1])
            else:
                start_times[task] = task.project.start_date

            finish_times[task] = start_times[task] + task.expected_time

        self.start = min(start_times.values())
        self.end = max(finish_times.values())

        for entry in self.graph:
            task = entry[0]
            self.blocks.append(Block(task, start_times[task],
                                     finish_times[task]))

    def topolgical_sort(self, graph_unsorted):
        graph_sorted = []

        graph_unsorted = dict(graph_unsorted)

        acyclic = False
        while graph_unsorted:
            for node, edges in list(graph_unsorted.items()):
                for edge in edges:
                    if edge in graph_unsorted:
                        break
                else:
                    acyclic = True
                    del graph_unsorted[node]
                    graph_sorted.append((node, edges))

        if not acyclic:
            raise RuntimeError("A cyclic dependency occurred")

        return graph_sorted

"""    def




public class CriticalPath {

  public static void main(String[] args) {
    //The example dependency graph from
    //http://www.ctl.ua.edu/math103/scheduling/scheduling_algorithms.htm
    HashSet<Task> allTasks = new HashSet<Task>();
    Task end = new Task("End", 0);
    Task F = new Task("F", 2, end);
    Task A = new Task("A", 3, end);
    Task X = new Task("X", 4, F, A);
    Task Q = new Task("Q", 2, A, X);
    Task start = new Task("Start", 0, Q);
    allTasks.add(end);
    allTasks.add(F);
    allTasks.add(A);
    allTasks.add(X);
    allTasks.add(Q);
    allTasks.add(start);
    System.out.println("Critical Path: "+Arrays.toString(criticalPath(allTasks)));
  }

  //A wrapper class to hold the tasks during the calculation
  public static class Task{
    //the actual cost of the task
    public int cost;
    //the cost of the task along the critical path
    public int criticalCost;
    //a name for the task for printing
    public String name;
    //the tasks on which this task is dependant
    public HashSet<Task> dependencies = new HashSet<Task>();
    public Task(String name, int cost, Task... dependencies) {
      this.name = name;
      this.cost = cost;
      for(Task t : dependencies){
        this.dependencies.add(t);
      }
    }
    @Override
    public String toString() {
      return name+": "+criticalCost;
    }
    public boolean isDependent(Task t){
      //is t a direct dependency?
      if(dependencies.contains(t)){
        return true;
      }
      //is t an indirect dependency
      for(Task dep : dependencies){
        if(dep.isDependent(t)){
          return true;
        }
      }
      return false;
    }
  }

  public static Task[] criticalPath(Set<Task> tasks){
    //tasks whose critical cost has been calculated
    HashSet<Task> completed = new HashSet<Task>();
    //tasks whose ciritcal cost needs to be calculated
    HashSet<Task> remaining = new HashSet<Task>(tasks);

    //Backflow algorithm
    //while there are tasks whose critical cost isn't calculated.
    while(!remaining.isEmpty()){
      boolean progress = false;

      //find a new task to calculate
      for(Iterator<Task> it = remaining.iterator();it.hasNext();){
        Task task = it.next();
        if(completed.containsAll(task.dependencies)){
          //all dependencies calculated, critical cost is max dependency
          //critical cost, plus our cost
          int critical = 0;
          for(Task t : task.dependencies){
            if(t.criticalCost > critical){
              critical = t.criticalCost;
            }
          }
          task.criticalCost = critical+task.cost;
          //set task as calculated an remove
          completed.add(task);
          it.remove();
          //note we are making progress
          progress = true;
        }
      }
      //If we haven't made any progress then a cycle must exist in
      //the graph and we wont be able to calculate the critical path
      if(!progress) throw new RuntimeException("Cyclic dependency, algorithm stopped!");
    }

    //get the tasks
    Task[] ret = completed.toArray(new Task[0]);
    //create a priority list
    Arrays.sort(ret, new Comparator<Task>() {

      @Override
      public int compare(Task o1, Task o2) {
        //sort by cost
        int i= o2.criticalCost-o1.criticalCost;
        if(i != 0)return i;

        //using dependency as a tie breaker
        //note if a is dependent on b then
        //critical cost a must be >= critical cost of b
        if(o1.isDependent(o2))return -1;
        if(o2.isDependent(o1))return 1;
        return 0;
      }
    });

    return ret;
  }
}"""
